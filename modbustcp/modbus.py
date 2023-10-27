#!/usr/bin/python3
import time
from api import api
from api import device

# Modbus/TCP
MODBUS_PORT = 502
# Modbus function code
READ_COILS = 0x01
READ_DISCRETE_INPUTS = 0x02
READ_HOLDING_REGISTERS = 0x03
READ_INPUT_REGISTERS = 0x04
WRITE_SINGLE_COIL = 0x05
WRITE_SINGLE_REGISTER = 0x06
WRITE_MULTIPLE_COILS = 0x0F
WRITE_MULTIPLE_REGISTERS = 0x10
WRITE_READ_MULTIPLE_REGISTERS = 0x17
ENCAPSULATED_INTERFACE_TRANSPORT = 0x2B
SUPPORTED_FUNCTION_CODES = (READ_COILS, READ_DISCRETE_INPUTS, READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS,
                            WRITE_SINGLE_COIL, WRITE_SINGLE_REGISTER, WRITE_MULTIPLE_COILS, WRITE_MULTIPLE_REGISTERS,
                            WRITE_READ_MULTIPLE_REGISTERS, ENCAPSULATED_INTERFACE_TRANSPORT)
# MEI type
MEI_TYPE_READ_DEVICE_ID = 0x0E
# Modbus except code
EXP_NONE = 0x00
EXP_ILLEGAL_FUNCTION = 0x01
EXP_DATA_ADDRESS = 0x02
EXP_DATA_VALUE = 0x03
EXP_SLAVE_DEVICE_FAILURE = 0x04
EXP_ACKNOWLEDGE = 0x05
EXP_SLAVE_DEVICE_BUSY = 0x06
EXP_NEGATIVE_ACKNOWLEDGE = 0x07
EXP_MEMORY_PARITY_ERROR = 0x08
EXP_GATEWAY_PATH_UNAVAILABLE = 0x0A
EXP_GATEWAY_TARGET_DEVICE_FAILED_TO_RESPOND = 0x0B
# Exception as short human-readable
EXP_TXT = {
    EXP_NONE: 'no exception',
    EXP_ILLEGAL_FUNCTION: 'illegal function',
    EXP_DATA_ADDRESS: 'illegal data address',
    EXP_DATA_VALUE: 'illegal data value',
    EXP_SLAVE_DEVICE_FAILURE: 'slave device failure',
    EXP_ACKNOWLEDGE: 'acknowledge',
    EXP_SLAVE_DEVICE_BUSY: 'slave device busy',
    EXP_NEGATIVE_ACKNOWLEDGE: 'negative acknowledge',
    EXP_MEMORY_PARITY_ERROR: 'memory parity error',
    EXP_GATEWAY_PATH_UNAVAILABLE: 'gateway path unavailable',
    EXP_GATEWAY_TARGET_DEVICE_FAILED_TO_RESPOND: 'gateway target device failed to respond'
}
# Exception as details human-readable
EXP_DETAILS = {
    EXP_NONE: 'The last request produced no exceptions.',
    EXP_ILLEGAL_FUNCTION: 'Function code received in the query is not recognized or allowed by slave.',
    EXP_DATA_ADDRESS: 'Data address of some or all the required entities are not allowed or do not exist in slave.',
    EXP_DATA_VALUE: 'Value is not accepted by slave.',
    EXP_SLAVE_DEVICE_FAILURE: 'Unrecoverable error occurred while slave was attempting to perform requested action.',
    EXP_ACKNOWLEDGE: 'Slave has accepted request and is processing it, but a long duration of time is required. '
                     'This response is returned to prevent a timeout error from occurring in the master. '
                     'Master can next issue a Poll Program Complete message to determine whether processing '
                     'is completed.',
    EXP_SLAVE_DEVICE_BUSY: 'Slave is engaged in processing a long-duration command. Master should retry later.',
    EXP_NEGATIVE_ACKNOWLEDGE: 'Slave cannot perform the programming functions. '
                              'Master should request diagnostic or error information from slave.',
    EXP_MEMORY_PARITY_ERROR: 'Slave detected a parity error in memory. '
                             'Master can retry the request, but service may be required on the slave device.',
    EXP_GATEWAY_PATH_UNAVAILABLE: 'Specialized for Modbus gateways, this indicates a misconfiguration on gateway.',
    EXP_GATEWAY_TARGET_DEVICE_FAILED_TO_RESPOND: 'Specialized for Modbus gateways, sent when slave fails to respond.'
}
# Module error codes
MB_NO_ERR = 0
MB_RESOLVE_ERR = 1
MB_CONNECT_ERR = 2
MB_SEND_ERR = 3
MB_RECV_ERR = 4
MB_TIMEOUT_ERR = 5
MB_FRAME_ERR = 6
MB_EXCEPT_ERR = 7
MB_CRC_ERR = 8
MB_SOCK_CLOSE_ERR = 9
# Module error as short human-readable
MB_ERR_TXT = {
    MB_NO_ERR: 'no error',
    MB_RESOLVE_ERR: 'name resolve error',
    MB_CONNECT_ERR: 'connect error',
    MB_SEND_ERR: 'socket send error',
    MB_RECV_ERR: 'socket recv error',
    MB_TIMEOUT_ERR: 'recv timeout occur',
    MB_FRAME_ERR: 'frame format error',
    MB_EXCEPT_ERR: 'modbus exception',
    MB_CRC_ERR: 'bad CRC on receive frame',
    MB_SOCK_CLOSE_ERR: 'socket is closed'
}
# Misc
MAX_PDU_SIZE = 253

""" pyModbusTCP utils functions """

import re
import socket
import struct


###############
# bits function
###############
def get_bits_from_int(val_int, val_size=16):
    """Get the list of bits of val_int integer (default size is 16 bits).

    Return bits list, the least significant bit first. Use list.reverse() for msb first.

    :param val_int: integer value
    :type val_int: int
    :param val_size: bit length of integer (word = 16, long = 32) (optional)
    :type val_size: int
    :returns: list of boolean "bits" (the least significant first)
    :rtype: list
    """
    bits = []
    # populate bits list with bool items of val_int
    for i in range(val_size):
        bits.append(bool((val_int >> i) & 0x01))
    # return bits list
    return bits


# short alias
int2bits = get_bits_from_int


def byte_length(bit_length):
    """Return the number of bytes needs to contain a bit_length structure.

    :param bit_length: the number of bits
    :type bit_length: int
    :returns: the number of bytes
    :rtype: int
    """
    return (bit_length + 7) // 8


def test_bit(value, offset):
    """Test a bit at offset position.

    :param value: value of integer to test
    :type value: int
    :param offset: bit offset (0 is lsb)
    :type offset: int
    :returns: value of bit at offset position
    :rtype: bool
    """
    mask = 1 << offset
    return bool(value & mask)


def set_bit(value, offset):
    """Set a bit at offset position.

    :param value: value of integer where set the bit
    :type value: int
    :param offset: bit offset (0 is lsb)
    :type offset: int
    :returns: value of integer with bit set
    :rtype: int
    """
    mask = 1 << offset
    return int(value | mask)


def reset_bit(value, offset):
    """Reset a bit at offset position.

    :param value: value of integer where reset the bit
    :type value: int
    :param offset: bit offset (0 is lsb)
    :type offset: int
    :returns: value of integer with bit reset
    :rtype: int
    """
    mask = ~(1 << offset)
    return int(value & mask)


def toggle_bit(value, offset):
    """Return an integer with the bit at offset position inverted.

    :param value: value of integer where invert the bit
    :type value: int
    :param offset: bit offset (0 is lsb)
    :type offset: int
    :returns: value of integer with bit inverted
    :rtype: int
    """
    mask = 1 << offset
    return int(value ^ mask)


########################
# Word convert functions
########################
def word_list_to_long(val_list, big_endian=True, long_long=False):
    """Word list (16 bits) to long (32 bits) or long long (64 bits) list.

    By default, word_list_to_long() use big endian order. For use little endian, set
    big_endian param to False. Output format could be long long with long_long.
    option set to True.

    :param val_list: list of 16 bits int value
    :type val_list: list
    :param big_endian: True for big endian/False for little (optional)
    :type big_endian: bool
    :param long_long: True for long long 64 bits, default is long 32 bits (optional)
    :type long_long: bool
    :returns: list of 32 bits int value
    :rtype: list
    """
    long_list = []
    block_size = 4 if long_long else 2
    # populate long_list (len is half or quarter of 16 bits val_list) with 32 or 64 bits value
    for index in range(int(len(val_list) / block_size)):
        start = block_size * index
        long = 0
        if big_endian:
            if long_long:
                long += (val_list[start] << 48) + (val_list[start + 1] << 32)
                long += (val_list[start + 2] << 16) + (val_list[start + 3])
            else:
                long += (val_list[start] << 16) + val_list[start + 1]
        else:
            if long_long:
                long += (val_list[start + 3] << 48) + (val_list[start + 2] << 32)
            long += (val_list[start + 1] << 16) + val_list[start]
        long_list.append(long)
    # return long list
    return long_list


# short alias
words2longs = word_list_to_long


def long_list_to_word(val_list, big_endian=True, long_long=False):
    """Long (32 bits) or long long (64 bits) list to word (16 bits) list.

    By default long_list_to_word() use big endian order. For use little endian, set
    big_endian param to False. Input format could be long long with long_long
    param to True.

    :param val_list: list of 32 bits int value
    :type val_list: list
    :param big_endian: True for big endian/False for little (optional)
    :type big_endian: bool
    :param long_long: True for long long 64 bits, default is long 32 bits (optional)
    :type long_long: bool
    :returns: list of 16 bits int value
    :rtype: list
    """
    word_list = []
    # populate 16 bits word_list with 32 or 64 bits value of val_list
    for val in val_list:
        block_l = [val & 0xffff, (val >> 16) & 0xffff]
        if long_long:
            block_l.append((val >> 32) & 0xffff)
            block_l.append((val >> 48) & 0xffff)
        if big_endian:
            block_l.reverse()
        word_list.extend(block_l)
    # return long list
    return word_list


# short alias
longs2words = long_list_to_word


##########################
# 2's complement functions
##########################
def get_2comp(val_int, val_size=16):
    """Get the 2's complement of Python int val_int.

    :param val_int: int value to apply 2's complement
    :type val_int: int
    :param val_size: bit size of int value (word = 16, long = 32) (optional)
    :type val_size: int
    :returns: 2's complement result
    :rtype: int
    :raises ValueError: if mismatch between val_int and val_size
    """
    # avoid overflow
    if not (-1 << val_size - 1) <= val_int < (1 << val_size):
        err_msg = 'could not compute two\'s complement for %i on %i bits'
        err_msg %= (val_int, val_size)
        raise ValueError(err_msg)
    # test negative int
    if val_int < 0:
        val_int += 1 << val_size
    # test MSB (do two's comp if set)
    elif val_int & (1 << (val_size - 1)):
        val_int -= 1 << val_size
    return val_int


# short alias
twos_c = get_2comp


def get_list_2comp(val_list, val_size=16):
    """Get the 2's complement of Python list val_list.

    :param val_list: list of int value to apply 2's complement
    :type val_list: list
    :param val_size: bit size of int value (word = 16, long = 32) (optional)
    :type val_size: int
    :returns: 2's complement result
    :rtype: list
    """
    return [get_2comp(val, val_size) for val in val_list]


# short alias
twos_c_l = get_list_2comp


###############################
# IEEE floating-point functions
###############################
def decode_ieee(val_int, double=False):
    """Decode Python int (32 bits integer) as an IEEE single or double precision format.

    Support NaN.

    :param val_int: a 32 or 64 bits integer as an int Python value
    :type val_int: int
    :param double: set to decode as a 64 bits double precision,
                   default is 32 bits single (optional)
    :type double: bool
    :returns: float result
    :rtype: float
    """
    if double:
        return struct.unpack("d", struct.pack("Q", val_int))[0]
    else:
        return struct.unpack("f", struct.pack("I", val_int))[0]


def encode_ieee(val_float, double=False):
    """Encode Python float to int (32 bits integer) as an IEEE single or double precision format.

    Support NaN.

    :param val_float: float value to convert
    :type val_float: float
    :param double: set to encode as a 64 bits double precision,
                   default is 32 bits single (optional)
    :type double: bool
    :returns: IEEE 32 bits (single precision) as Python int
    :rtype: int
    """
    if double:
        return struct.unpack("Q", struct.pack("d", val_float))[0]
    else:
        return struct.unpack("I", struct.pack("f", val_float))[0]


################
# misc functions
################
def crc16(frame):
    """Compute CRC16.

    :param frame: frame
    :type frame: bytes
    :returns: CRC16
    :rtype: int
    """
    crc = 0xFFFF
    for item in frame:
        next_byte = item
        crc ^= next_byte
        for _ in range(8):
            lsb = crc & 1
            crc >>= 1
            if lsb:
                crc ^= 0xA001
    return crc


def valid_host(host_str):
    """Validate a host string.

    Can be an IPv4/6 address or a valid hostname.

    :param host_str: the host string to test
    :type host_str: str
    :returns: True if host_str is valid
    :rtype: bool
    """
    # IPv4 valid address ?
    try:
        socket.inet_pton(socket.AF_INET, host_str)
        return True
    except socket.error:
        pass
    # IPv6 valid address ?
    try:
        socket.inet_pton(socket.AF_INET6, host_str)
        return True
    except socket.error:
        pass
    # valid hostname ?
    if len(host_str) > 255:
        return False
    # strip final dot, if present
    if host_str[-1] == '.':
        host_str = host_str[:-1]
    # validate each part of the hostname (part_1.part_2.part_3)
    re_part_ok = re.compile('(?!-)[a-z0-9-_]{1,63}(?<!-)$', re.IGNORECASE)
    return all(re_part_ok.match(part) for part in host_str.split('.'))

""" pyModbusTCP Client """

from dataclasses import dataclass, field
import random
import socket
from socket import AF_UNSPEC, SOCK_STREAM
import struct
from typing import Dict


class ModbusClient:
    """Modbus TCP client."""

    class _InternalError(Exception):
        pass

    class _NetworkError(_InternalError):
        def __init__(self, code, message):
            self.code = code
            self.message = message

    class _ModbusExcept(_InternalError):
        def __init__(self, code):
            self.code = code

    def __init__(self, addrkey, timeout=3, debug=False, auto_open=True, auto_close=False):
        """Constructor.

        :param host: hostname or IPv4/IPv6 address server address
        :type host: str
        :param port: TCP port number
        :type port: int
        :param unit_id: unit ID
        :type unit_id: int
        :param timeout: socket timeout in seconds
        :type timeout: float
        :param debug: debug state
        :type debug: bool
        :param auto_open: auto TCP connect
        :type auto_open: bool
        :param auto_close: auto TCP close)
        :type auto_close: bool
        :return: Object ModbusClient
        :rtype: ModbusClient
        """
        # private
        # internal variables
        self._host = None
        self._port = None
        self._unit_id = None
        self._timeout = None
        self._debug = None
        self._auto_open = None
        self._auto_close = None
        self._sock = socket.socket()
        self._transaction_id = 0  # MBAP transaction ID
        self._last_error = MB_NO_ERR  # last error code
        self._last_except = EXP_NONE  # last except code
        # public
        # constructor arguments: validate them with property setters
        self.host = addrkey.split(':')[0]
        self.port = int(addrkey.split(':')[1])
        self.timeout = timeout
        self.debug = debug
        self.auto_open = auto_open
        self.auto_close = auto_close
        self.dev = device.device(addrkey=addrkey, create={"type":"com-port", "name":"ModBUS " + addrkey.split(':')[0]}, threaded=True)
        self.log = self.dev.log
        self.dev.onStatusCallBack(self.onStatus)

    def __repr__(self):
        r_str = 'ModbusClient(host=\'%s\', port=%d, unit_id=%d, timeout=%.2f, debug=%s, auto_open=%s, auto_close=%s)'
        r_str %= (self.host, self.port, self.unit_id, self.timeout, self.debug, self.auto_open, self.auto_close)
        return r_str

    def __del__(self):
        self.close()

    @property
    def last_error(self):
        """Last error code."""
        return self._last_error

    @property
    def last_error_as_txt(self):
        """Human-readable text that describe last error."""
        return MB_ERR_TXT.get(self._last_error, 'unknown error')

    @property
    def last_except(self):
        """Return the last modbus exception code."""
        return self._last_except

    @property
    def last_except_as_txt(self):
        """Short human-readable text that describe last modbus exception."""
        default_str = 'unreferenced exception 0x%X' % self._last_except
        return EXP_TXT.get(self._last_except, default_str)

    @property
    def last_except_as_full_txt(self):
        """Verbose human-readable text that describe last modbus exception."""
        default_str = 'unreferenced exception 0x%X' % self._last_except
        return EXP_DETAILS.get(self._last_except, default_str)

    @property
    def host(self):
        """Get or set the server to connect to.

        This can be any string with a valid IPv4 / IPv6 address or hostname.
        Setting host to a new value will close the current socket.
        """
        return self._host

    @host.setter
    def host(self, value):
        # check type
        if type(value) is not str:
            raise TypeError('host must be a str')
        # check value
        if valid_host(value):
            if self._host != value:
                self.close()
                self._host = value
            return
        # can't be set
        raise ValueError('host can\'t be set (not a valid IP address or hostname)')

    @property
    def port(self):
        """Get or set the current TCP port (default is 502).

        Setting port to a new value will close the current socket.
        """
        return self._port

    @port.setter
    def port(self, value):
        # check type
        if type(value) is not int:
            raise TypeError('port must be an int')
        # check validity
        if 0 < value < 65536:
            if self._port != value:
                self.close()
                self._port = value
            return
        # can't be set
        raise ValueError('port can\'t be set (valid if 0 < port < 65536)')

    @property
    def unit_id(self):
        """Get or set the modbus unit identifier (default is 1).

        Any int from 0 to 255 is valid.
        """
        return self._unit_id

    @unit_id.setter
    def unit_id(self, value):
        # check type
        if type(value) is not int:
            raise TypeError('unit_id must be an int')
        # check validity
        if 0 <= value <= 255:
            self._unit_id = value
            return
        # can't be set
        raise ValueError('unit_id can\'t be set (valid from 0 to 255)')

    @property
    def timeout(self):
        """Get or set requests timeout (default is 30 seconds).

        The argument may be a floating point number for sub-second precision.
        Setting timeout to a new value will close the current socket.
        """
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        # enforce type
        value = float(value)
        # check validity
        if 0 < value < 3600:
            if self._timeout != value:
                self.close()
                self._timeout = value
            return
        # can't be set
        raise ValueError('timeout can\'t be set (valid between 0 and 3600)')

    @property
    def debug(self):
        """Get or set the debug flag (True = turn on)."""
        return self._debug

    @debug.setter
    def debug(self, value):
        # enforce type
        self._debug = bool(value)

    @property
    def auto_open(self):
        """Get or set automatic TCP connect mode (True = turn on)."""
        return self._auto_open

    @auto_open.setter
    def auto_open(self, value):
        # enforce type
        self._auto_open = bool(value)

    @property
    def auto_close(self):
        """Get or set automatic TCP close after each request mode (True = turn on)."""
        return self._auto_close

    @auto_close.setter
    def auto_close(self, value):
        # enforce type
        self._auto_close = bool(value)

    @property
    def is_open(self):
        """Get current status of the TCP connection (True = open)."""
        return self._sock.fileno() > 0

    def onStatus(self, data):
        self.log.log("MB: Got status: {}".format(data))
        if len(data)<4:
            self.log.log("Incorrect request. too short", "RED")
            return
        if data[-2:] == b'\xcc\x16':
            data = data[:-2]
        try:
            ret = self._req_pdu(data)
            self.log.log("Returned: {}".format(ret))
            self.dev.setStatus(ret+b'\xcc\x16')
        except Exception as err:
            self.log.log("Exception: {}".format(err), "RED")
            self.log.log("Closing connection", "YELLOW")
            if self.is_open:
                self.close()

    def open(self):
        """Connect to modbus server (open TCP connection).

        :returns: connect status (True on success)
        :rtype: bool
        """
        try:
            self._open()
            return True
        except ModbusClient._NetworkError as e:
            self._req_except_handler(e)
            return False

    def _open(self):
        """Connect to modbus server (open TCP connection)."""
        # open an already open socket -> reset it
        if self.is_open:
            self.close()
        # init socket and connect
        # list available sockets on the target host/port
        # AF_xxx : AF_INET -> IPv4, AF_INET6 -> IPv6,
        #          AF_UNSPEC -> IPv6 (priority on some system) or 4
        # list available socket on target host
        for res in socket.getaddrinfo(self.host, self.port, AF_UNSPEC, SOCK_STREAM):
            af, sock_type, proto, canon_name, sa = res
            try:
                self._sock = socket.socket(af, sock_type, proto)
            except socket.error:
                continue
            try:
                self._sock.settimeout(self.timeout)
                self._sock.connect(sa)
            except socket.error:
                self._sock.close()
                continue
            break
        # check connect status
        if not self.is_open:
            raise ModbusClient._NetworkError(MB_CONNECT_ERR, 'connection refused')

    def close(self):
        """Close current TCP connection."""
        self._sock.close()

    def custom_request(self, pdu):
        """Send a custom modbus request.

        :param pdu: a modbus PDU (protocol data unit)
        :type pdu: bytes
        :returns: modbus frame PDU or None if error
        :rtype: bytes or None
        """
        # make request
        try:
            return self._req_pdu(pdu)
        # handle errors during request
        except ModbusClient._InternalError as e:
            self._req_except_handler(e)
            return None

    def _send(self, frame):
        """Send frame over current socket.

        :param frame: modbus frame to send (MBAP + PDU)
        :type frame: bytes
        """
        # check socket
        if not self.is_open:
            raise ModbusClient._NetworkError(MB_SOCK_CLOSE_ERR, 'try to send on a close socket')
        # send
        try:
            self._sock.send(frame)
        except socket.timeout:
            self._sock.close()
            raise ModbusClient._NetworkError(MB_TIMEOUT_ERR, 'timeout error')
        except socket.error:
            self._sock.close()
            raise ModbusClient._NetworkError(MB_SEND_ERR, 'send error')

    def _send_pdu(self, pdu):
        """Convert modbus PDU to frame and send it.

        :param pdu: modbus frame PDU
        :type pdu: bytes
        """
        # for auto_open mode, check TCP and open on need
        if self.auto_open and not self.is_open:
            self._open()
        # add MBAP header to PDU
        tx_frame = self._add_mbap(pdu)
        # send frame with error check
        self._send(tx_frame)
        # debug
        self._debug_dump('Tx', tx_frame)

    def _recv(self, size):
        """Receive data over current socket.

        :param size: number of bytes to receive
        :type size: int
        :returns: receive data or None if error
        :rtype: bytes
        """
        try:
            r_buffer = self._sock.recv(size)
        except socket.timeout:
            self._sock.close()
            raise ModbusClient._NetworkError(MB_TIMEOUT_ERR, 'timeout error')
        except socket.error:
            r_buffer = b''
        # handle recv error
        if not r_buffer:
            self._sock.close()
            raise ModbusClient._NetworkError(MB_RECV_ERR, 'recv error')
        return r_buffer

    def _recv_all(self, size):
        """Receive data over current socket, loop until all bytes is received (avoid TCP frag).

        :param size: number of bytes to receive
        :type size: int
        :returns: receive data or None if error
        :rtype: bytes
        """
        r_buffer = b''
        while len(r_buffer) < size:
            r_buffer += self._recv(size - len(r_buffer))
        return r_buffer

    def _recv_pdu(self, min_len=2):
        """Receive the modbus PDU (Protocol Data Unit).

        :param min_len: minimal length of the PDU
        :type min_len: int
        :returns: modbus frame PDU or None if error
        :rtype: bytes or None
        """
        # receive 6 bytes header (MBAP)
        rx_mbap = self._recv_all(6)
        # decode MBAP
        (f_transaction_id, f_protocol_id, f_length) = struct.unpack('>HHH', rx_mbap)
        # check MBAP fields
        f_transaction_err = f_transaction_id != self._transaction_id
        f_protocol_err = f_protocol_id != 0
        f_length_err = f_length >= 256
        #f_unit_id_err = f_unit_id != self.unit_id
        # checking error status of fields
        if f_transaction_err or f_protocol_err or f_length_err: # or f_unit_id_err:
            self.close()
            self._debug_dump('Rx', rx_mbap)
            raise ModbusClient._NetworkError(MB_RECV_ERR, 'MBAP checking error')
        # recv PDU
        rx_pdu = self._recv_all(f_length)
        # for auto_close mode, close socket after each request
        if self.auto_close:
            self.close()
        # dump frame
        self._debug_dump('Rx', rx_mbap + rx_pdu)
        # body decode
        # check PDU length for global minimal frame (an except frame: func code + exp code)
        if len(rx_pdu) < 2:
            raise ModbusClient._NetworkError(MB_RECV_ERR, 'PDU length is too short')
        # extract function code
        rx_fc = rx_pdu[1]
        # check except status
        if rx_fc >= 0x80:
            exp_code = rx_pdu[2]
            raise ModbusClient._ModbusExcept(exp_code)
        # check PDU length for specific request set in min_len (keep this after except checking)
        if len(rx_pdu) < min_len:
            raise ModbusClient._NetworkError(MB_RECV_ERR, 'PDU length is too short for current request')
        # if no error, return PDU
        return rx_pdu

    def _add_mbap(self, pdu):
        """Return full modbus frame with MBAP (modbus application protocol header) append to PDU.

        :param pdu: modbus PDU (protocol data unit)
        :type pdu: bytes
        :returns: full modbus frame
        :rtype: bytes
        """
        # build MBAP
        self._transaction_id = random.randint(0, 65535)
        protocol_id = 0
        length = len(pdu)
        mbap = struct.pack('>HHH', self._transaction_id, protocol_id, length)
        self.unit_id = pdu[0]
        # full modbus/TCP frame = [MBAP]PDU
        return mbap + pdu

    def _req_pdu(self, tx_pdu, rx_min_len=2):
        """Request processing (send and recv PDU).

        :param tx_pdu: modbus PDU (protocol data unit) to send
        :type tx_pdu: bytes
        :param rx_min_len: min length of receive PDU
        :type rx_min_len: int
        :returns: the receive PDU or None if error
        :rtype: bytes
        """
        # init request engine
        self._req_init()
        # send PDU
        self._send_pdu(tx_pdu)
        # return receive PDU
        return self._recv_pdu(min_len=rx_min_len)

    def _req_init(self):
        """Reset request status flags."""
        self._last_error = MB_NO_ERR
        self._last_except = EXP_NONE

    def _req_except_handler(self, _except):
        """Global handler for internal exceptions."""
        # on request network error
        if isinstance(_except, ModbusClient._NetworkError):
            self._last_error = _except.code
            self._debug_msg(_except.message)
        # on request modbus except
        if isinstance(_except, ModbusClient._ModbusExcept):
            self._last_error = MB_EXCEPT_ERR
            self._last_except = _except.code
            self._debug_msg('modbus exception (code %d "%s")' % (self.last_except, self.last_except_as_txt))

    def _debug_msg(self, msg):
        """Print debug message if debug mode is on.

        :param msg: debug message
        :type msg: str
        """
        if self.debug:
            print(msg)

    def _debug_dump(self, label, frame):
        """Print debug dump if debug mode is on.

        :param label: head label
        :type label: str
        :param frame: modbus frame
        :type frame: bytes
        """
        if self.debug:
            self._pretty_dump(label, frame)

    @staticmethod
    def _pretty_dump(label, frame):
        """Dump a modbus frame.

        modbus/TCP format: [MBAP] PDU

        :param label: head label
        :type label: str
        :param frame: modbus frame
        :type frame: bytes
        """
        # split data string items to a list of hex value
        dump = ['%02X' % c for c in frame]
        # format message
        dump_mbap = ' '.join(dump[0:7])
        dump_pdu = ' '.join(dump[7:])
        msg = '[%s] %s' % (dump_mbap, dump_pdu)
        # print result
        print(label)
        print(msg)

try:
    from api import report
    report.sendReport("ltplugin-modbus.service")
except Exception as e:
    print("Error sending report: {}".format(e))

config = open("/home/sh2/plugins/shsp-modbus-tcp-args.txt", 'r').read()
a = None
devs = {}
for c in config.split("\n"):
    p = c.strip().split(' ')
    if len(p) == 2:
        if p[0]=='modbus-devices':
            if not a:
                a = api.APIThread(name="shsp-modbus-tcp", debug=False)
            devs[p[1]] = ModbusClient(p[1])

while True:
    time.sleep(1)
