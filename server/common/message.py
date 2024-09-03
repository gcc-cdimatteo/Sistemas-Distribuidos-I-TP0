from common.utils import Bet

class Message:
    def __init__(self, content):
        self.content = content
        self.type = None

        messages = self.content.split('\n')
        if '|' in messages[0]: self.type = "BET" ## there can be bets, we will be sure after the processing

    def empty(self):
        return self.content == "" or len(self.content) == 0

    def is_BET(self): return self.type == "BET"

    def get_bets(self) -> tuple[list[Bet], int]:
        rejected = 0
        bets = []
        for bet in self.content.split('\n'):
            values = bet.split('|')
            if len(values) < 5: break
            try:
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
            except:
                rejected += 1

        return (bets, rejected)

    def get_agency_id(self) -> int: return self.content.split('\n')[0].split('|')[1]