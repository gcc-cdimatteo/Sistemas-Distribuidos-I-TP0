import socket
import logging
import signal
from multiprocessing import Process, Barrier, Manager
from common.message import Message
from common.client import Client
from common.utils import Bet, store_bets, load_bets, has_won

class Server:
    MAX_CLIENTS = 5

    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._server_running = True

        manager = Manager()

        ## Clients Management
        self.winners_barrier = manager.Barrier(Server.MAX_CLIENTS) ## ONLY WORKS FOR 5 AGENCIES - TODO: fix
        self.clients_connected = manager.list()
        self.clients_connected_lock = manager.Lock()

        ## Bets Management
        self.bets = manager.list()
        self.bets_lock = manager.Lock()
        self.bets_file_lock = manager.Lock()

        signal.signal(signal.SIGTERM, self.handle_exit)
    
    def handle_exit(self, signum, frame):
        self._server_running = False
        logging.debug(f"_handle_exit - try to aquire clients connected lock")
        self.clients_connected_lock.acquire()
        logging.debug(f"_handle_exit - aquire clients connected lock")
        for client in self.clients_connected:
            logging.warn(f'connection with address {client} gracefully closed')
            client.close()
        self.clients_connected_lock.release()
        logging.debug(f"_handle_exit - release clients connected lock")
        self._server_socket.close()
        logging.warn(f'server gracefully exited')

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """
        logging.info(f"action: start server | result: in progress")

        processes: list[Process] = []

        while self._server_running:
            logging.info(f"action: start server | result: running")
            client_sock = self.__accept_new_connection()
            if client_sock != None:
                processes.append(Process(target=self.__handle_client_connection, args=(client_sock,)))
                processes[-1].start()

        logging.info(f"action: start server | result: stopped")

        logging.info(f"action: process management | result: in progress")

        for p in processes:
            try:
                p.join()
            except:
                logging.error(f"process didn't closed successfully: name = {p.name}, id = {p.pid}")
                logging.critical(f"forcing process to shutdown: in progress")
                logging.critical(f"SIGTERM sent to process returned [{p.terminate()}]")
                logging.critical(f"forcing process to shutdown: finished")
        
        logging.info(f"action: process management | result: success")

    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            logging.info(f"action: receive_message | status: in progress")

            client = self.start_client(client_sock)
            while not client.finished:
                client = self.process_message(client)
            
            logging.info(f"action: receive_message | status: finished | client: {client}")
        except OSError as e:
            logging.error(f"action: receive_message | result: fail | error: {e}")

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
    
    def start_client(self, socket) -> Client:
        logging.debug(f"start_client - try to aquire clients connected lock")
        self.clients_connected_lock.acquire()
        logging.debug(f"start_client - aquire clients connected lock")

        self.clients_connected.append(socket)
        logging.debug(f"start_client - append socket")

        self.clients_connected_lock.release()
        logging.debug(f"start_client - release clients connected lock")

        client = Client(socket)
        logging.debug(f"create new client {client}")

        return client

    def finish_client(self, client: Client):
        client.finish()
        client.close()
    
    def process_message(self, client: Client):
        msg = client.recv()

        logging.debug(f"MESSAGE RECEIVED: {msg.content}")

        if msg.empty(): return

        if msg.is_BET(): 
            rejected = self.process_bets(msg)
            if rejected != 0: 
                client.send(f"REJECTED {rejected}\n")
            else:
                client.send(f"ACK\n")

        elif msg.is_END():
            client.send(f"END ACK\n")
            logging.debug('action: receive_end | result: success')
            self.process_winners() ## blocks until last client
        
        elif msg.is_CON():
            logging.debug('action: receive_ask_winners | result: in progress')
            client.id = msg.get_agency_id()
            logging.debug(f'client updated: {client}')
            self.return_winners(client)
            logging.debug('action: receive_ask_winners | result: success')
            self.finish_client(client)
        
        else:
            logging.error("action: receive_message | result: fail | error: message couldnt be parsed")
        
        return client
    
    def process_bets(self, msg: Message) -> int:
        (bets, rejected_bets) = msg.get_bets()

        if (rejected_bets != 0):
            logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets)}")
            logging.warn(f"action: apuestas rechazadas | result: fail | cantidad: {rejected_bets}")
        else:    
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
        
        self.bets_file_lock.acquire()
        store_bets(bets)
        self.bets_file_lock.release()

        return rejected_bets

    def process_winners(self):
        if self.winners_barrier.n_waiting == Server.MAX_CLIENTS - 1: ## last ask
            self.bets_lock.acquire() ## at this point nobody should have the lock
            self.bets[:] = list(load_bets())
            self.bets_lock.release()
            logging.info('action: sorteo | result: success')
        
        self.winners_barrier.wait()

    def return_winners(self, client: Client):
        winners = self.load_winners(client)
        client.send(f"{'|'.join([winner.document for winner in winners])}\n")
    
    def load_winners(self, client: Client) -> list[Bet]:
        logging.debug(f'load_winners - try to acquire winners lock - client {client}')
        self.bets_lock.acquire()
        logging.debug(f'load_winners - acquire winners lock - client {client}')

        winners: list[Bet] = []

        logging.debug(f'client {client} - self.bets has {len(self.bets)} rows')

        for bet in self.bets:
            if int(bet.agency) == int(client.id) and has_won(bet):
                winners.append(bet)

        logging.debug(f'winners for client {client} are {winners} rows')

        self.bets_lock.release()
        logging.debug(f'load_winners - release winners lock - client {client}')
        
        return winners