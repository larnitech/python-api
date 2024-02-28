import sys

import threading
import time
import socket
import struct
import json, yaml
import requests
import crcmod

from api import api
from api import device

class modbus(object):
    def __init__(self, addr, config=None):
        self.api = api.api_class
        self.log = api.api_class.log
        self.config = config
        self.addr = addr
        self.log.log("Modbus protocol for {} created".format(addr))
        self.dev = device.device(addr=addr, threaded=False, onStatus=self.event, onConnect=self.onConnect)
        self.crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
        self.wait_addr = None
        self.wait_func = None
        self.wait_res = None

    def onConnect(self):
        if self.config: # Change device hardware parameters according to provided
            self.api.setHW(f"{self.addr.split(':')[0]}:98", f"cfg='{self.config}'")

    def event(self, data):
        if 'status' not in data or 'hex' not in data['status']:
            self.log.log(f"Incorrect modbus event: {data}", "RED")
            return False
        data = data['status']['hex']
        if len(data)<5:
            self.log.log("Error. Too short modbus data: {}".format(data), "RED")
        if not data or len(data)<8: return
        d = bytes().fromhex(data[2:])
        #check CRC
        crc = self.crc16(d[:-2])
        if ((d[-1]<<8)|d[-2]) != crc:
            self.log.log("Packet CRC missmuch. {} != {}".format((d[-1]<<8)|d[-2], crc), "RED")
        #self.log.log("Answer from modbus {} func {}".format(d[0], d[1]))
        if self.wait_addr == d[0] and self.wait_func == d[1]:
            if self.wait_func == 3:
                self.wait_res = d[3:-2]
                return
            if self.wait_func == 16:
                return True
        self.log.log("a: {}/{}, f:{}/{}".format(self.wait_addr, d[0], self.wait_func, d[1]))

    def nums(self, data, l):
        res = [0]*(len(data)//l)
        for i in range(len(data)):
            res[i//l]|= data[i]<<((l - i%l - 1)*8)
        return res

    def read(self, maddr, addr, func=3, len=1, timeout=0.5, numlen=None):
        if func==3:
            req = bytes([maddr, func, addr>>8, addr&0xFF, len>>8, len&0xFF])
        crc = self.crc16(req)
        req+= bytes([crc&0xff, crc>>8])
        self.wait_addr = maddr
        self.wait_func = func
        self.wait_res = None
        self.api.setStatus(self.addr, req)
        t = time.monotonic()
        while (t+timeout)>=time.monotonic():
            if self.wait_res:
                return self.wait_res if not numlen else self.nums(self.wait_res, numlen)
        self.log.log("ERROR: Modbus timeout", "YELLOW")
        return None

    def write(self, maddr, addr, data, func=16, len=1, timeout=0.4):
        if func==16:
            req = bytes([maddr, func, addr>>8, addr&0xFF, len>>8, len&0xFF, len*2])+data
        crc = self.crc16(req)
        req+= bytes([crc&0xff, crc>>8])
        self.wait_addr = maddr
        self.wait_func = func
        self.wait_res = None
        self.api.setStatus(self.addr, req)
        t = time.monotonic()
        while (t+timeout)>=time.monotonic():
            if self.wait_res:
                return self.wait_res if not numlen else self.nums(self.wait_res, numlen)
        self.log.log("ERROR: Modbus timeout", "YELLOW")
        return None
