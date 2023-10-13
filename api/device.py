import time
import datetime
import sys
import json
import api

class device(object):
    def __init__(self, addr=None, addrkey=None, create={}, threaded=True):
        self.api = api.api
        self.log = self.api.log
        self.addr = addr
        self.addrkey = addrkey
        self.create = create
        self.threaded = threaded
        if self.threaded:
            self.thread = threading.Thread(target=self.loop, args=())
            self.thread.daemon = True
            self.thread.start()
            watcher.threads['API'] = self.thread
        self.api.setConnectCallback(self.onConnect)

    def onConnect(self):
        self.log.log("API connected")

    def loop(self):
        while True:
            time.sleep(1)
