# radio_fast.py A simple nRF24L01 point-to-point half duplex protocol for fixed length messages.
# (C) Copyright Peter Hinch 2016
# Released under the MIT licence

import pyb
from nrf24l01 import NRF24L01, POWER_3, SPEED_250K
from config import FromMaster, ToMaster         # User defined message classes and hardware config

class RadioFast(NRF24L01):
    pipes = (b'\xf0\xf0\xf0\xf0\xe1', b'\xf0\xf0\xf0\xf0\xd2')
    timeout = 100
    def __init__(self, master, config):
        super().__init__(pyb.SPI(config.spi_no), pyb.Pin(config.csn_pin), pyb.Pin(config.ce_pin), config.channel, FromMaster.payload_size())
        if master:
            self.open_tx_pipe(RadioFast.pipes[0])
            self.open_rx_pipe(1, RadioFast.pipes[1])
        else:
            self.open_tx_pipe(RadioFast.pipes[1])
            self.open_rx_pipe(1, RadioFast.pipes[0])
        self.set_power_speed(POWER_3, SPEED_250K) # Best range for point to point links
        self.start_listening()

    def get_latest_msg(self, msg_rx):
        if self.any():
            while self.any():                   # Discard any old buffered messages
                data = self.recv()
            msg_rx.store(data)                  # Can raise OSError but only as a result of programming error
            return True
        return False

    def sendbuf(self, msg_send):
        self.stop_listening()
        try:
            self.send(msg_send.pack(), timeout = self.timeout)
        except OSError:
            self.start_listening()
            return False
        self.start_listening()
        return True

    def await_message(self, msg_rx):
        start = pyb.millis()
        while pyb.elapsed_millis(start) <= self.timeout:
            try:
                if self.get_latest_msg(msg_rx):
                    return True
            except OSError:
                pass                            # Bad message length. Try again.
        return False                            # Timeout

class Master(RadioFast):
    def __init__(self, config):
        super().__init__(True, config)

    def exchange(self, msg_send):               # Call when transmit-receive required.
        msg_rx = ToMaster()
        if self.sendbuf(msg_send):
            if self.await_message(msg_rx):
                self.stop_listening()
                return msg_rx.unpack()
        self.stop_listening()
        return None                             # Timeout

class Slave(RadioFast):
    def __init__(self, config):
        super().__init__(False, config)

    def exchange(self, msg_send, block = True):
        if block:                               # Blocking read returns message on success,
            while not self.any():               # None on timeout
                pass
        else:                                   # Nonblocking read returns message on success,
            if not self.any():                  # None on timeout, False on no data
                return False
        msg_rx = FromMaster()
        if self.await_message(msg_rx):
            if self.sendbuf(msg_send):
                return msg_rx.unpack()
        return None                             # Timeout
