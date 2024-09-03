import socket
import logging
import signal
from common.message import Message
from common.utils import Bet, load_bets, has_won, store_bets, get_msg_length, get_full_message, send_full_message

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self.server_running = True
        
        self.clients_connected = set()
        self.clients_finished = 0

        self.bets = None

        signal.signal(signal.SIGTERM, self._handle_exit)
    
    def _handle_exit(self, signum, frame):
        self.server_running = False
        for client in self.clients_connected:
            logging.warn(f'connection with address {client} gracefully closed')
            client.close()
        self._server_socket.close()
        logging.warn(f'server gracefully exited')

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """
        while self.server_running:
            client_sock = self.__accept_new_connection()
            if client_sock != None:
                self.__handle_client_connection(client_sock)

    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            msg_length = get_msg_length(client_sock)

            msg = get_full_message(client_sock, msg_length)

            ## Save Client Address
            addr = client_sock.getpeername()
            self.clients_connected.add(addr[0])

            self.process_message(Message(msg), client_sock)
        except OSError as e:
            logging.error("action: receive_message | result: fail | error: {e}")
        finally:
            client_sock.close()

    def __accept_new_connection(self):
        """
        Accept new connections

        Function blocks until a connection to a client is made.
        Then connection created is printed and returned
        """
        try:
            # Connection arrived
            logging.info('action: accept_connections | result: in_progress')
            c, addr = self._server_socket.accept()
            logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
            return c
        except:
            logging.warn('socket closed')
            return None
    
    def process_message(self, msg: Message, socket):
        if msg.empty(): return

        if msg.is_END():
            self.clients_finished += 1
            send_full_message(socket, f"END ACK\n".encode('utf-8'))
            logging.debug('action: receive_end | result: success')
        
        elif msg.is_WIN():
            logging.debug('action: receive_ask_winners | result: in progress')

            logging.debug(f'action: receive_ask_winners | clients_finished: {self.clients_finished}')
            logging.debug(f'action: receive_ask_winners | clients_connected: {self.clients_connected}')

            if self.clients_finished == len(self.clients_connected):
                send_full_message(socket, f"Y\n".encode('utf-8'))
                if self.bets == None: self.bets = list(load_bets())
                logging.debug(f'action: load bets | result: success | count: {len(self.bets)}')
            else:
                send_full_message(socket, f"N\n".encode('utf-8'))
            logging.debug('action: receive_ask_winners | result: success')
        
        elif msg.is_CON():
            logging.debug('action: receive_consult | result: in progress')
            id = msg.get_agency_id()
            winners = self.get_winners(id)
            winners_message = '|'.join([winner.document for winner in winners])
            logging.debug(f'about to send message {winners_message}')
            send_full_message(socket, f"{winners_message}\n".encode('utf-8'))
            logging.debug('action: receive_consult | result: success')
        
        elif msg.is_BET(): 
            (received, rejected) = self.process_bets(msg)
            if rejected != 0: send_full_message(socket, f"REJECTED: {rejected}\n".encode('utf-8'))
            else: send_full_message(socket, f"ACK\n".encode('utf-8'))
        else:
            logging.error("action: receive_message | result: fail | error: message couldnt be parsed")
    
    def process_bets(self, msg: Message) -> tuple[int, int]:
        (bets, rejected_bets) = msg.get_bets()

        if (rejected_bets != 0):
            logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets)}")
            logging.warn(f"action: apuestas rechazadas | result: fail | cantidad: {rejected_bets}")
        else:    
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
        
        store_bets(bets)

        return (len(bets), rejected_bets)

    def get_winners(self, id: int) -> list[Bet]:
        winners = []

        for bet in self.bets:
            if bet.agency == int(id) and has_won(bet): 
                winners.append(bet)

        return winners
