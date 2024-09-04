import socket
import logging
import signal
from common.message import Message
from common.client import Client
from common.utils import store_bets

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._server_running = True

        self.clients = set()
        
        self.bets = None

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
            client = Client(client_sock)

            self.clients.add(client)

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
    
    def process_message(self, client: Client):
        msg = client.recv()

        if msg.empty(): return

        if msg.is_BET(): 
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
