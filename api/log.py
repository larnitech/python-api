import time
import datetime
import sys
import json

class LogThread(object):
    def __init__(self):
        self.sln = False
        return

    def silent(self, s):
        self.sln = s

    def log(self, msg, color='WHITE', dict=None):
        if self.sln:
            return
        if dict:
            msg = msg + json.dumps(dict, indent=4)
        r="\u001b[0m"
        c=r
        if color=='WHITE':
            c="\u001b[37;1m"
        if color=='RED':
            c="\u001b[31;1m"
        if color=='GREEN':
            c="\u001b[32;1m"
        if color=='YELLOW':
            c="\u001b[33;1m"
        if color=='BLUE':
            c="\u001b[34;1m"
        print("{}.{:03.0f}  {}{}{}".format(datetime.datetime.now().strftime("%H:%M:%S"), datetime.datetime.now().microsecond / 1000.0, c, msg, r))
        sys.stdout.flush()
