import logging
import re

def remove_ansi_escape_sequences(text):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class ANSIFilter(logging.Filter):
    def filter(self, record):
        record.msg = remove_ansi_escape_sequences(record.msg)
        return True
