import time
import datetime
import sys
import json
import threading
import queue
from api import api
from api import watcher

class device(object):
    def __init__(self, addr=None, addrkey=None, create={}, threaded=True):
        self.api = api.api_class
        self.log = api.api_class.log
        self.addr = addr
        self.addrkey = addrkey
        self.create = create
        self.threaded = threaded
        self.statusCB = None
        if self.threaded:
            self.q = queue.Queue(10)
            self.thread = threading.Thread(target=self.loop, args=())
            self.thread.daemon = True
            self.thread.start()
            watcher.threads['dev-{}-{}'.format(addrkey, addr)] = self.thread
        self.api.setConnectCallback(self._onConnect)
        if self.create!={}:
            if self.addrkey:
                self.create['addr-key'] = self.addrkey
            elif self.addr:
                self.create['addr'] = self.addr
            self.api.register(self.create, self)

    def _onConnect(self):
        self.onConnect()

    def onConnect(self):
        self.log.log("API connected")

    def _onCreate(self, data):
        if 'addr' in data:
            self.addr = data['addr']
        self.onCreate()

    def onCreate(self):
        self.log.log("Device created")

    def _onStatus(self, data):
        if self.threaded:
            self.q.put(data, block=True, timeout=0.1)
        else:
            self.onStatus(data)

    def onStatusCallBack(self, cb):
        self.statusCB = cb

    def onStatus(self, data):
        self.log.log("Received status: {}".format(data))
        if self.statusCB:
            return self.statusCB(data)
        return True

    def setStatus(self, data):
        self.log.log("Sending status: {}".format(data))
        if type(data).__name__ == 'bytes':
            data = '0x'+data.hex()
        if self.addrkey:
            self.api.request('she-device-status', {"addr-key": self.addrkey, "status": data})
        elif self.addr:
            self.api.request('she-device-status', {"addr": self.addr, "status": data})

    def loop(self):
        while True:
            ret = self.q.get(block=True, timeout=None)
            if ret:
                self.onStatus(ret)
