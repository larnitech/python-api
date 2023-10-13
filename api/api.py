import threading
import time
import sys
import socket
import struct
import json
import log
import watcher

api = None

class APIThread(object):
    def __init__(self, host=None, port=None, key=None, timeout=3, onConnect=None, callBack=None, debug=False):
        self.log = log.LogThread()
        self.unix_sockets = ['/tmp/sh.socket', '/home/sh2/sh.sock']
        self.connected = False
        self.sock = None
        self.host = host
        self.port = port if port else 2040
        self.key = key
        self.dbg = debug
        self.timeout = timeout
        self.cb = [callBack] if callBack else []
        self.connect_cb = [onConnect] if onConnect else []
        self.connected = False

        self.thread = threading.Thread(target=self.run, args=())
        self.thread.daemon = True
        self.thread.start()
        watcher.threads['API'] = self.thread
        api = self

    def debug(self, d):
        self.dbg = d

    def send(self, js):
        d = b'-JSON-' + json.dumps(js).encode()
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
                    res = data
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

    def connect(self):
        if self.sock:
            del self.sock
            self.sock = None
        if self.host:
            host = self.host
        else:
            for i in self.unix_sockets:
                if os.file_exists(i):
                    host = i
                    break
        self.log.log("Connecting to {}".format(host), 'BLUE')
        if host[0]=='/': # unix socket
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            try:
                self.sock.connect(host)
                self.connected = True
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
                    for cb in self.connect_cb:
                        cb()
            js = None
            while True:
                try:
                    st, js = self.read()
                    if not st:
                        self.connected = False
                        break
                except socket.timeout:
                        if self.dbg:
                            self.log.log('timeout')
                        continue
                except Exception as err:
                    st = False
                    self.log.log("Error reading packet. disconnecting. error: {}".format(err), 'RED')
                    self.connected = False
                    break
                if self.cb!=[] and st and js:
                    for cb in self.cb:
                        ret = cb(js)
                        if type(ret).__name__ == 'dict':
                            self.send(ret)
                        elif ret == True:
                            break
                else:
                    time.sleep(0.01)
