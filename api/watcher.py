import threading
from api import log
import time
import sys
import os

threads = {}

def run():
    l = log.LogThread()
    while True:
        for k,v in threads.items():
            if not v.is_alive():
                l.log("{} thread is dead, exiting".format(k), 'RED')
                time.sleep(1)
                os._exit(1)
        time.sleep(1)

thread = threading.Thread(target=run, args=())
thread.daemon = True
thread.start()
