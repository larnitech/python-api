import threading
import time
import sys
import os
import socket
import struct
import json
from api import log
from api import watcher

api_class = None
REGISTER_DELAY = 1

class APIThread(object):
    def __init__(self, host=None, port=None, key=None, name=None, timeout=3, onConnect=None, callBack=None, debug=False):
        global api_class
        api_class = self
        self.log = log.LogThread()
        self.unix_sockets = ['/tmp/sh.socket', '/home/sh2/sh.sock']
        self.connected = False
        self.sock = None
        self.host = host
        self.port = port if port else 2040
        self.key = key
        self.name = name
        self.dbg = debug
        self.timeout = timeout
        self.cb = [callBack] if callBack else []
        self.connect_cb = [onConnect] if onConnect else []
        self.connected = False
        self.addrs = {}
        self.addrkeys = {}
        self.devs = []
        self.tregdevs = 0

        self.thread = threading.Thread(target=self.run, args=())
        self.thread.daemon = True
        self.thread.start()
        watcher.threads['API'] = self.thread

    def debug(self, d):
        self.dbg = d

    def send(self, js):
        d = b'-JSON-' + json.dumps(js, ensure_ascii=False).encode('utf-8')
        if self.dbg:
            self.log.log("API sending: {}".format(d))
        data = struct.pack("I", len(d)) + d;
        size = 0
        while size<len(data):
            try:
                ret = self.sock.send(data[size:])
            except Exception as err:
                self.log.log("Error sending data to socket: {}".format(err), 'RED')
                self.reconnect()
                return False
            if ret:
                size = size + ret
            else:
                self.log.log("Error sending data. result: {}".format(ret), "RED")
                return False
        return True

    def register(self, devinfo, c):
        if 'addr-key' in devinfo:
            self.addrkeys[devinfo['addr-key']] = c
            found = False
            for i in range(len(self.devs)):
                if 'addr-key' in self.devs[i] and self.devs[i]['addr-key'] == devinfo['addr-key']:
                    found = True
                    self.devs[i] = devinfo
                    if self.dbg:
                        self.log.log("Updating device info")
                    break
            if not found:
                if self.dbg:
                    self.log.log("Registering new device {}".format(devinfo))
                self.devs.append(devinfo)
        elif 'addr' in devinfo:
            self.addrs[devinfo['addr']] = c
            found = False
            for i in range(len(self.devs)):
                if 'addr' in self.devs[i] and self.devs[i]['addr'] == devinfo['addr']:
                    found = True
                    self.devs[i] = devinfo
                    if self.dbg:
                        self.log.log("Updating device info")
                    break
            if not found:
                if self.dbg:
                    self.log.log("Registering new device {}".format(devinfo))
                self.devs.append(devinfo)
        self.tregdevs = time.time() + REGISTER_DELAY

    def register_commit(self):
        if self.devs != []:
            self.log.log("Commiting registration of {} devices".format(len(self.devs)))
            self.request('she-register-pnp', {"pnp": self.devs})
        self.tregdevs = 0

    def request(self, type, param=None, auth=0):
        if not self.sock or (not auth and not self.connected):
            self.log.log("Request error. API not connected", "RED")
            return False
        q = {'request':type}
        if param:
            q.update(param)
        if self.dbg:
            self.log.log("Request: {}".format(q))
        return self.send(q)

    def setCallback(self, cb):
        self.cb.append(cb)

    def reconnect(self):
        self.connected = False
        if self.sock:
            self.sock.close()

    def setConnectCallback(self, cb):
        if cb not in self.connect_cb:
            self.connect_cb.append(cb)
        if self.connected:
                cb()

    def read(self, auth=0):
        if not self.sock or (not auth and not self.connected):
            self.log.log("Read error. API not connected", "RED")
            return False, None
        ret = self.sock.recv(4, socket.MSG_WAITALL)
        if len(ret) == 4:
            size = struct.unpack("I", ret)[0]
            if size>0 and size<256000:
                data = b''
                while len(data)<size:
                    ret = self.sock.recv(size-len(data))
                    #self.log.log("recv = {}".format(ret))
                    data = data + ret
                    time.sleep(0.01)
            #self.log.log("size = {}".format(size))
            try:
                if data[:5] == b'<?xml':
                    self.xmlReceived(data)
                    return False, None
                elif data[:6] == b'-JSON-':
                    res = json.loads(data[6:].decode())
                else:
                    res = json.loads(data.decode())
            except Exception as err:
                self.log.log("Error decoding response json: {}. Error: {}".format(data, err), 'RED')
                return False, None
            if self.dbg:
                self.log.log("Received: {}".format(res if type(res).__name__ != 'bytes' else res[:100]))
            return True, res
        else:
            #self.log.log("recv = {}".format(ret))
            return False, None

        return True, None

    def xmlReceived(self, xml):
        self.log.log("XML Received")

    def onReceive(self, data):
        if 'event' in data and data['event']=='she-device-is-created':
            if 'addr-key' in data and data['addr-key'] in self.addrkeys:
                self.addrkeys[data['addr-key']]._onCreate(data)
            elif 'addr' in data and data['addr'] in self.addrs:
                self.addrs[data['addr']]._onCreate(data)
        elif 'event' in data and data['event']=='she-device-status' and 'status' in data:
            if type(data['status']).__name__ == 'str' and len(data['status'])>3 and data['status'][:2]=='0x':
                status = bytes().fromhex(data['status'][2:])
            else:
                status = data['status']
            if 'addr-key' in data and data['addr-key'] in self.addrkeys:
                self.addrkeys[data['addr-key']]._onStatus(status)
            elif 'addr' in data and data['addr'] in self.addrs:
                self.addrs[data['addr']]._onStatus(status)

        if self.cb!=[]:
            for cb in self.cb:
                ret = cb(data)
                if type(ret).__name__ == 'dict':
                    self.send(ret)

    def connect(self):
        host = None
        if self.sock:
            del self.sock
            self.sock = None
        if self.host:
            host = self.host
        else:
            for i in self.unix_sockets:
                if os.path.exists(i):
                    host = i
                    break
            if not host:
                self.log.log("Unix sockets dose not exists", 'RED')
                return False
        self.log.log("Connecting to {}".format(host), 'BLUE')
        if host[0]=='/': # unix socket
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            try:
                self.sock.connect(host)
                self.connected = True
                self.log.log('API connected', 'GREEN')
                if self.name:
                    self.request('setup', {"appId": self.name})
                return True
            except Exception as e:
                self.log.log("API: Connect error: {}".format(e))
                del self.sock
                self.sock = None
                return False
        else: # TCP connection
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            try:
                self.sock.connect((self.host,int(self.port)))
            except Exception as e:
                self.log.log("API: Connect error: {}".format(e))
                del self.sock
                self.sock = None
                return False
            self.request('authorize', {'key':self.key}, auth=True)
            st, js = self.read(auth=True)
            if not st:
                self.log.log("API: Error while receiving auth response", 'RED')
                del self.sock
                self.sock = None
                return False
            if st and js and 'response' in js and js['response']=='authorize':
                if 'result' in js and js['result'] == 'success':
                    self.log.log('API connected and authorized', 'GREEN')
                    self.connected = True
                    if self.name:
                        self.request('setup', {"appId": self.name})
                    return True
                else:
                    self.log.log('API: auth response error: {}'.format(js), 'GREEN')
                    del self.sock
                    self.sock = None
                    return False
            else:
                self.log.log('Waiting for authorize packet. received: {}'.format(js), 'YELLOW')
                del self.sock
                self.sock = None
                return False

    def run(self):
        self.abort = False
        while not self.abort:
            while not self.abort and not self.connected:
                if not self.connect():
                    time.sleep(3)
                    continue
                else:
                    # call connect callbacks
                    self.register_commit()
                    for cb in self.connect_cb:
                        cb()
            js = None
            while True:
                if self.tregdevs and (self.tregdevs<time.time() or (self.tregdevs-REGISTER_DELAY-1)>time.time()):
                     self.register_commit()
                try:
                    st, js = self.read()
                    if not st:
                        self.connected = False
                        break
                except socket.timeout:
                        #if self.dbg:
                        #    self.log.log('timeout')
                        continue
                except Exception as err:
                    st = False
                    self.log.log("Error reading packet. disconnecting. error: {}".format(err), 'RED')
                    self.connected = False
                    break
                if st and js:
                    self.onReceive(js)
                else:
                    time.sleep(0.01)
