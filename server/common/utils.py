import csv
import datetime
import time
import logging
import struct

""" Bets storage location. """
STORAGE_FILEPATH = "bets.csv"
""" Simulated winner number in the lottery contest. """
LOTTERY_WINNER_NUMBER = 7574


""" A lottery bet registry. """
class Bet:
    def __init__(self, agency: str, first_name: str, last_name: str, document: str, birthdate: str, number: str):
        """
        agency must be passed with integer format.
        birthdate must be passed with format: 'YYYY-MM-DD'.
        number must be passed with integer format.
        """
        self.agency = int(agency)
        self.first_name = first_name
        self.last_name = last_name
        self.document = document
        self.birthdate = datetime.date.fromisoformat(birthdate)
        self.number = int(number)

""" Checks whether a bet won the prize or not. """
def has_won(bet: Bet) -> bool:
    return bet.number == LOTTERY_WINNER_NUMBER

"""
Persist the information of each bet in the STORAGE_FILEPATH file.
Not thread-safe/process-safe.
"""
def store_bets(bets: list[Bet]) -> None:
    with open(STORAGE_FILEPATH, 'a+') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
        for bet in bets:
            writer.writerow([bet.agency, bet.first_name, bet.last_name,
                             bet.document, bet.birthdate, bet.number])
            logging.info(f'action: apuesta_almacenada | result: success | dni: {bet.document} | numero: {bet.number}')

"""
Get Bets from client message
"""
def get_bets(msg: str) -> list[Bet]:
    bets = []
    for bet in msg.split('\n'):
        values = bet.split('|')
        if len(values) < 5: return bets
        logging.debug(f"append bet with values {values}")
        bets.append(
            Bet(
                agency = values[0],
                first_name = values[1],
                last_name = values[2],
                document = values[3],
                birthdate = values[4],
                number = values[5]
            )
        )
    return bets

"""
Loads the information all the bets in the STORAGE_FILEPATH file.
Not thread-safe/process-safe.
"""
def load_bets() -> list[Bet]:
    with open(STORAGE_FILEPATH, 'r') as file:
        reader = csv.reader(file, quoting=csv.QUOTE_MINIMAL)
        for row in reader:
            yield Bet(row[0], row[1], row[2], row[3], row[4], row[5])

def get_msg_length(socket) -> int:
    raw_msg_length = socket.recv(4)
    if not raw_msg_length: return 0
    return struct.unpack('!I', raw_msg_length)[0]

def get_full_message(socket, msg_length) -> str:
    msg = b''
    while len(msg) < msg_length:
        packet = socket.recv(msg_length - len(msg))
        if not packet: return
        msg += packet
    
    return msg.decode('utf-8')

def send_full_message(socket, msg):
    bytes_sent = 0
    while bytes_sent < len(msg):
        last_sent = socket.send(msg)
        if last_sent == 0: 
            logging.info(f'action: send_full_message | result: fail | error: socket closed')
            return
        bytes_sent += last_sent