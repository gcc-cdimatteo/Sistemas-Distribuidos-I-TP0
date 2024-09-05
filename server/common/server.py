import socket
import logging
import signal
from multiprocessing import Process, Barrier, Manager
from common.message import Message
from common.client import Client
from common.utils import Bet, store_bets, load_bets, has_won

class Server:
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._server_running = True

        manager = Manager()

        ## Clients Management
        self.winners_barrier = manager.Barrier(5) ## ONLY WORKS FOR 5 AGENCIES - TODO: fix
        self.clients = manager.list()
        self.clients_lock = manager.Lock()
        
        ## Bets Management
        self.bets = manager.list()
        self.bets_lock = manager.Lock()
        self.bets_file_lock = manager.Lock()

        signal.signal(signal.SIGTERM, self._handle_exit)
    
    def _handle_exit(self, signum, frame):
        self._server_running = False
        logging.debug(f"_handle_exit - try to aquire clients lock")
        self.clients_lock.acquire()
        logging.debug(f"aquire clients lock")
        for client in self.clients:
            logging.warn(f'connection with address {client} gracefully closed')
            client.close()
        self.clients_lock.release()
        self._server_socket.close()
        logging.warn(f'server gracefully exited')

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """
        processes: list[Process] = []
        
        while self._server_running:
            client_sock = self.__accept_new_connection()
            if client_sock != None:
                processes.append(Process(target=self.__handle_client_connection, args=(client_sock,)))
                processes[-1].start()
        
        for p in processes:
            try:
                p.close()
            except:
                logging.error(f"process didn't closed successfully: name = {p.name}, id = {p.pid}")
                logging.critical(f"forcing process to shutdown: in progress")
                logging.critical(f"SIGTERM sent to process returned [{p.terminate()}]")
                logging.critical(f"forcing process to shutdown: finished")

    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            client = self.start_client(client_sock)
            while not client.finished:
                self.process_message(client)

                logging.debug(f'__handle_client_connection - try to acquire clients lock - client: {client}')
                self.clients_lock.acquire()
                logging.debug(f'__handle_client_connection - acquire clients lock - client: {client}')
                logging.debug(f'__handle_client_connection - self.clients:')
                for c in self.clients: 
                    if client.ip == c.ip: 
                        logging.debug(f'__handle_client_connection - c is: {client}')
                        client = c
                    break

                self.clients_lock.release()
                logging.debug(f'__handle_client_connection - release clients lock - client: {client}')

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
        client = Client(socket)
        logging.debug(f"create new client {client}")
        logging.debug(f"add_client - try to aquire clients lock")
        self.clients_lock.acquire()
        logging.debug(f"aquire clients lock")
        self.clients.append(client)
        logging.debug(f"append {client} to {self.clients}")
        self.clients_lock.release()
        logging.debug(f"release clients lock")
        return client

    def finish_client(self, client: Client):
        logging.debug(f"finish_client - try to aquire clients lock")
        self.clients_lock.acquire()
        logging.debug(f"aquire clients lock")

        client.finish()
        logging.debug(f"finish client {client}")

        all_clients_finished = True

        logging.debug(f"self.clients:")
        for c in self.clients: logging.debug(f"{c}")
        
        for c in self.clients:
            if not c.finished: 
                logging.debug(f"client {c} didnt finish yet")
                all_clients_finished = False
                break

        client.close()
        logging.debug(f"close client socket")

        self.clients_lock.release()
        logging.debug(f"release clients lock")

        if all_clients_finished: 
            logging.debug(f"shutdown server")
            self._server_running = False
    
    def process_message(self, client: Client):
        msg = client.recv()

        logging.debug(f"MESSAGE RECEIVED from {client}: {msg.content}")

        logging.debug(f'process_message - try to acquire clients lock - client: {client}')
        self.clients_lock.acquire()
        logging.debug(f'process_message - acquire clients lock - client: {client}')
        logging.debug(f'process_message - self.clients:')
        for c in self.clients: logging.debug(f'process_message - {c}')

        self.clients_lock.release()
        logging.debug(f'process_message - release clients lock - client: {client}')

        if msg.empty(): return

        if msg.is_BET(): 
            (agency, rejected) = self.process_bets(msg)
            self.change_client_id(client, agency)
            logging.debug(f"msg.is_BET() - client is: {client}")
            if rejected != 0: 
                client.send(f"REJECTED {rejected}\n")
            else:
                client.send(f"ACK\n")

        elif msg.is_END():
            client.send(f"END ACK\n")
            logging.debug('action: receive_end | result: success')
            self.process_winners() ## blocks until last client, then load bets
        
        elif msg.is_CON():
            logging.debug(f"client is: {client}")
            logging.debug('action: receive_ask_winners | result: in progress')
            self.return_winners(client)
            logging.debug('action: receive_ask_winners | result: success')
            self.finish_client(client)
        
        else:
            logging.error("action: receive_message | result: fail | error: message couldnt be parsed")
    
    def process_bets(self, msg: Message) -> tuple[int, int]:
        (bets, rejected_bets) = msg.get_bets()

        if (rejected_bets != 0):
            logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets)}")
            logging.warn(f"action: apuestas rechazadas | result: fail | cantidad: {rejected_bets}")
        else:    
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
        
        self.bets_file_lock.acquire()
        store_bets(bets)
        self.bets_file_lock.release()

        return (bets[0].agency, rejected_bets)

    def change_client_id(self, client, agency):
        if client.id != 0: return

        logging.debug(f'change_client_id - try to acquire clients lock - client: {client}')
        self.clients_lock.acquire()
        logging.debug(f'change_client_id - acquire clients lock - client: {client}')

        logging.debug(f'change_client_id - self.clients before change:')
        for c in self.clients: logging.debug(f"{c}")
        
        mut_client = None
        mut_pos = 0

        for c in self.clients: 
            if c.ip == client.ip: 
                mut_client = c
                break
            mut_pos += 1
        
        mut_client.set_id(agency)

        self.clients[mut_pos] = mut_client

        logging.debug(f'change_client_id - self.clients after change:')
        for c in self.clients: logging.debug(f"{c}")

        self.clients_lock.release()
        logging.debug(f'change_client_id - release clients lock - client: {mut_client}')
    
    def process_winners(self):
        logging.debug(f'---- wait for winner in progress')

        if self.winners_barrier.n_waiting == 4: ## last ask
            self.bets_lock.acquire() ## at this point nobody should have the lock
            self.bets[:] = list(load_bets())
            self.load_winners()
            self.bets_lock.release()
            logging.info('action: sorteo | result: success')

        logging.debug(f'---- wait for winner finished')
        
        self.winners_barrier.wait()

    def load_winners(self):
        winners = {}
        for bet in self.bets:
            if has_won(bet):
                if bet.agency not in winners: winners[bet.agency] = []
                winners[bet.agency].append(bet)
        
        logging.debug(f'try to acquire clients lock')
        self.clients_lock.acquire()
        logging.debug(f'acquire clients lock')
        logging.debug(f'self.clients:')
        for c in self.clients: logging.debug(f'{c}')

        for c in self.clients:
            c.set_winners(winners[c.id])

        self.clients_lock.release()
        logging.debug(f'release clients lock')
    
    def return_winners(self, client: Client):
        client.send(f"{'|'.join([winner.document for winner in client.winners])}\n")