import socket
import logging
import signal
from common.message import Message
from common.client import Client
from common.utils import Bet, store_bets, load_bets, has_won

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._server_running = True

        self.clients: set[Client] = set()
        
        self.winners: list[Bet] = []

        signal.signal(signal.SIGTERM, self._handle_exit)
    
    def _handle_exit(self, signum, frame):
        self._server_running = False
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
        while self._server_running:
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
            client = self.add_client(client_sock)

            self.process_message(client)
        except OSError as e:
            logging.error("action: receive_message | result: fail | error: {e}")
        finally:
            client.close()

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
    
    def add_client(self, socket) -> Client:
        ip = socket.getpeername()[0]
        for c in self.clients:
            if c.ip == ip:
                c.set_new_socket(socket)
                return c
        
        client = Client(socket)
        self.clients.add(client)
        return client
    
    def process_message(self, client: Client):
        msg = client.recv()

        if msg.empty(): return

        if msg.is_END():
            client.finish()
            client.send(f"END ACK\n")
            logging.debug('action: receive_end | result: success')
        
        elif msg.is_WIN():
            logging.debug('action: receive_ask_winners | result: in progress')

            for c in self.clients:
                if not c.finished:
                    logging.debug('action: receive_ask_winners | result: no winners yet')
                    client.send(f"N\n")
                    return
            
            if len(self.winners) == 0: self.load_winners()
            logging.debug('action: receive_ask_winners | result: success')
            client.send(f"Y\n")

            logging.debug(f'action: load bets | result: success | count: {len(self.winners)}')
                    
        elif msg.is_CON():
            logging.debug('action: receive_consult | result: in progress')
            id = msg.get_agency_id()
            local_winners = self.get_local_winners(id)
            winners_message = '|'.join([winner.document for winner in local_winners])
            logging.debug(f'about to send message {winners_message}')
            client.send(f"{winners_message}\n")
            logging.debug('action: receive_consult | result: success')
        
        elif msg.is_BET(): 
            (_, rejected) = self.process_bets(msg)
            if rejected != 0: 
                client.send(f"REJECTED {rejected}\n")
            else:
                client.send(f"ACK\n")
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
    
    def load_winners(self):
        for b in load_bets():
            if has_won(b): self.winners.append(b)
        
    def get_local_winners(self, id: int) -> list[Bet]:
        return [b for b in self.winners if int(b.agency) == int(id)]
