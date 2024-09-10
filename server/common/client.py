import struct
import logging

from common.message import Message
from common.utils import Bet

class Client:
    def __init__(self, socket):
        self.id = 0
        self.socket = socket
        self.ip = socket.getpeername()[0]
        self.winners = None
        self.finished = False

    def close(self): self.socket.close()

    def finish(self): self.finished = True

    def set_id(self, id): 
        if self.id == 0: 
            logging.debug(f'set id for client {self}')
            self.id = id
    
    def set_winners(self, winners: list[Bet]): 
        self.winners = winners

    def read_exactly(self, n):
        msg = b''
        while len(msg) < n:
            packet = self.socket.recv(n - len(msg))
            if not packet:
                return None
            msg += packet
        
        return msg
    
    def recv(self) -> Message:
        content_length = struct.unpack('>I', self.read_exactly(4))[0]
        
        msg = self.read_exactly(content_length)
        
        return Message(msg.decode('utf-8'))

    def send(self, content):
        content_bytes = content.encode('utf-8')

        content_length = struct.pack('>I', len(content_bytes))
        
        full_message = content_length + content_bytes
        
        bytes_sent = 0
        while bytes_sent < len(full_message):
            last_sent = self.socket.send(full_message[bytes_sent:])
            if last_sent == 0:
                logging.info(f'action: send_full_message | result: fail | error: socket closed')
                return
            bytes_sent += last_sent
    
    def __str__(self) -> str:
        return f"[id: {self.id}, ip: {self.ip}, finished: {self.finished}]"