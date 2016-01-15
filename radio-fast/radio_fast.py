# radio-fast
import pyb
from nrf24l01 import NRF24L01, POWER_3, SPEED_250K
from config import FromMaster, ToMaster

class MessagePair(object):
    def __init__(self):
        self.from_master = FromMaster()
        self.to_master = ToMaster()
        assert self.from_master.payload_size == self.to_master.payload_size, 'config.py: ToMaster and FromMaster messages have mismatched payload sizes/formats'

class RadioFast(NRF24L01):
    pipes = (b'\xf0\xf0\xf0\xf0\xe1', b'\xf0\xf0\xf0\xf0\xd2')
    timeout = 100
    def __init__(self, master, config, msg):
        self.msg = msg
        super().__init__(pyb.SPI(config.spi_no), pyb.Pin(config.csn_pin), pyb.Pin(config.ce_pin), config.channel, msg.payload_size)
        if master:
            self.open_tx_pipe(RadioFast.pipes[0])
            self.open_rx_pipe(1, RadioFast.pipes[1])
        else:
            self.open_tx_pipe(RadioFast.pipes[1])
            self.open_rx_pipe(1, RadioFast.pipes[0])
        self.set_power_speed(POWER_3, SPEED_250K) # Best range for point to point links
        self.start_listening()

    def get_latest_msg(self):
        if self.any():
            while self.any():                   # Discard any old buffered messages
                data = self.recv()
            self.msg.store(data)                # Can raise OSError
            return True
        return False

    def sendbuf_old(self):
        self.stop_listening()
        start = pyb.millis()
        done = False
        while not done:
            try:
                self.send(self.msg.pack(), timeout = self.timeout)
            except OSError:
                pass                            # It may fail early: if so keep trying while rx might be listening
            else:
                done = True
            if not done and pyb.elapsed_millis(start) >= self.timeout:
                self.start_listening()
                return False
        self.start_listening()
        return True

    def sendbuf(self):
        self.stop_listening()
        try:
            self.send(self.msg.pack(), timeout = self.timeout)
        except OSError:
            self.start_listening()
            return False
        self.start_listening()
        return True

    def await_message(self):
        start = pyb.millis()
        while pyb.elapsed_millis(start) <= self.timeout:
            try:
                if self.get_latest_msg():
                    return True
            except OSError:
                pass                            # Bad message length. Try again.
        return False                            # Timeout

class Master(RadioFast):
    def __init__(self, config, message_pair):
        super().__init__(True, config, message_pair.from_master)

    def exchange(self):                         # Call when transmit-receive required.
        if self.sendbuf():
            if self.await_message():
                self.stop_listening()
                return self.msg.unpack()
        self.stop_listening()
        return None                             # Timeout

class Slave(RadioFast):
    def __init__(self, config, message_pair):
        super().__init__(False, config, message_pair.to_master)

    def exchange(self, block=False):
        if block:                               # Blocking read returns message on success,
            while not self.any():               # None on timeout
                pass
        else:                                   # Nonblocking read returns message on success,
            if not self.any():                  # None on timeout, False on no data
                return False
        if self.await_message():
            if self.sendbuf():
                return self.msg.unpack()
        return None                             # Timeout
