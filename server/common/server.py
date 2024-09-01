import socket
import logging
import signal
from common.utils import store_bets, get_bets, get_msg_length, get_full_message, send_full_message

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self.clients_connected = []
        self._server_running = True

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
            msg_length = get_msg_length(client_sock)

            msg = get_full_message(client_sock, msg_length)

            ## Save Client Address
            addr = client_sock.getpeername()
            self.clients_connected.append(addr)

            ## Store Bets
            store_bets(get_bets(msg))

            ## Resend message
            send_full_message(client_sock, "{}\n".format(msg).encode('utf-8'))
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