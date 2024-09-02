from common.utils import Bet

class Message:
    def __init__(self, content):
        self.content = content
        self.type = None
    
    def empty(self):
        return self.content == "" or len(self.content) == 0

    def deserialize(self):
        messages = self.content.split('\n')
        if len(messages) == 0: return
        
        if messages[0] == "END": self.type = "END"
        elif messages[0] == "WIN": self.type = "WIN"
        elif "CON" in messages[0]: self.type = "CON"
        elif '|' in messages[0]: self.type = "BET" ## there can be bets, we will be sure after the processing
    
    def is_END(self): return self.type == "END"

    def is_WIN(self): return self.type == "WIN"

    def is_CON(self): return self.type == "CON"

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