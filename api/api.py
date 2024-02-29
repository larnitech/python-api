import threading
import time
import sys
import os
import socket
import struct
import json
import xml.etree.ElementTree as ET

from api import log
from api import watcher

api_class = None
REGISTER_DELAY = 1

class APIThread(object):
    def __init__(self, host=None, port=None, key=None, name=None, timeout=3, onConnect=None, callBack=None, debug=False, apiPath=None):
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
        self.cb = [{'cb':callBack, 'type':None}] if callBack else []
        self.xmlCB = []
        self.connect_cb = [onConnect] if onConnect else []
        self.connected = False
        self.addrs = {}
        self.addrkeys = {}
        self.devs = []
        self.tregdevs = 0
        self.subs = []
        self.tsubs = 0
        self.subsDevs = {}
        self.xml = None
        self.xmlRoot = None

        if apiPath:
            if apiPath[0]=='/': # UnixSocket
                self.host = apiPath
            else:
                tmp = apiPath.split(':')
                self.host = tmp[0]
                if len(tmp)>1:
                    self.port = int(tmp[1])
                if len(tmp)>2:
                    self.key = tmp[2]

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
        self.tregdevs = time.monotonic() + REGISTER_DELAY

    def subscribe(self, addr, c, delay=1):
        if self.subs == []:
            self.tsubs = time.monotonic()+delay
        if addr not in self.subs:
            self.subs.append(addr)
        if addr not in self.subsDevs:
            self.subsDevs[addr] = [c]
        elif c not in self.subsDevs[addr]:
            self.subsDevs[addr].append(c)

    def subscribe_commit(self):
        self.request('status-subscribe', {"status":"detailed", 'addr':self.subs})
        self.tsubs = 0

    def register_commit(self):
        if self.devs != []:
            self.log.log("Commiting registration of {} devices".format(len(self.devs)))
            self.request('she-register-pnp', {"pnp": self.devs})
        self.tregdevs = 0

    def request(self, type, param=None, auth=0):
        if not self.sock or (not auth and not self.connected):
            self.log.log(f"Request error. API not connected: {type}", "RED")
            return False
        q = {'request':type}
        if param:
            q.update(param)
        if self.dbg:
            self.log.log("Request: {}".format(q))
        return self.send(q)

    def setCallback(self, cb, type=None):
        self.cb.append({'cb':cb, 'type':type})

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
                    return True, None
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
        self.xml = xml
        for cb in self.xmlCB:
            cb(xml)

    def setXMLcb(self, cb):
        if cb not in self.xmlCB:
            if self.xmlCB == []:
                self.xmlCB.append(cb)
                if self.connected:
                    self.request('logic-subscribe')
            else:
                self.xmlCB.append(cb)

    def _onXML(self, data):
        if self.xmlRoot:
            del self.xmlRoot
            self.xmlRoot = None

    def getXMLRoot(self):
        self.setXMLcb(self._onXML)
        if not self.xml:
            for i in range(round(timeout*10)):
                time.sleep(0.1)
                if self.xml:
                    break
        if not self.xmlRoot and self.xml:
            self.log.log("Parsing XML")
            parser = ET.XMLParser(encoding="utf-8")
            self.xmlRoot = ET.fromstring(self.xml.decode().replace("&", ''), parser=parser)
            self.parent_map = {c: p for p in self.xmlRoot.iter() for c in p}
            return self.xmlRoot
        return None

    def getItem(self, addr, timeout=1):
        self.getXMLRoot()
        if not self.xmlRoot:
            return None
        i=self.xmlRoot.findall('.//item[@addr="{}"]'.format(addr))
        return None if i==[] else i[0].attrib

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
        elif self.subsDevs and (('response' in data and data['response'] == 'status-subscribe') or ('event' in data and data['event'] == 'statuses')) and 'devices' in data:
            for d in data['devices']:
                if 'addr' in d and d['addr'] in self.subsDevs:
                    for cb in self.subsDevs[d['addr']]:
                        cb._onStatus(d)

        if self.cb!=[]:
            for cb in self.cb:
                if not cb['type'] or ('request' in data and data['request']==cb['type']) or ('event' in data and data['event']==cb['type']):
                    ret = cb['cb'](data)
                    if type(ret).__name__ == 'dict':
                        self.send(ret)

    def _onConnect(self):
        if self.name:
            self.request('setup', {"appId": self.name})
        if self.xmlCB != []:
            self.request('logic-subscribe')
        self.subscribe_commit()
        self.register_commit()

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
                    self._onConnect()
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

    def setStatus(self, addr, data):
        if type(data).__name__ == 'bytes':
            hex = '0x' + data.hex()
        elif type(data).__name__ == 'str':
            hex = '0x' + data.encode().hex()
        elif type(data).__name__ == 'dict':
            hex = data
        else:
            self.log.log("setStatus Incorrect data type. Expected bytes/str/dict", "RED")
            return False
        self.request('status-set', {"addr": addr, "status": hex})

    def setHW(self, addr, hw):
        hex = f"{addr} {hw}".encode().hex()
        self.request('status-set', {"addr": "1000:15", "status": hex})

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
                if self.tregdevs and self.tregdevs<time.monotonic():
                     self.register_commit()
                if self.tsubs and self.tsubs<time.monotonic():
                     self.subscribe_commit()
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
