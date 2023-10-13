import threading
import log

threads = {}

def run():
    log = log.LogThread()
    while True:
        for k,v in threads.items():
            if not v.is_alive():
                log.log("{} thread is dead, exiting".format(k), 'RED')
                time.sleep(1)
                exit(1)
        time.sleep(1)

thread = threading.Thread(target=run, args=())
thread.daemon = True
thread.start()
