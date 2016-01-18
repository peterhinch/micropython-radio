# config.py Configuration file for radio_fast.py
# This contains the user defined configuration
# (C) Copyright Peter Hinch 2016
# Released under the MIT licence
import ustruct
from msg import RadioConfig, msg

# Choose a channel (or accept default 99)
#RadioConfig.channel = 99
# Modify for your hardware
testbox_config = RadioConfig(spi_no = 1, csn_pin = 'X5', ce_pin = 'Y11') # My testbox
v1_config = RadioConfig(spi_no = 1, csn_pin = 'X5', ce_pin = 'X4')   # V1 Micropower PCB
# config_v2 = RadioConfig(spi_no = 1, csn_pin = 'X5', ce_pin = 'X2')    # V2 Micropower PCB

# For both messages need to alter fmt, instance variables, pack() and unpack() methods, to suit application.
# Both messages must pack to the same length otherwise an assertion failure will occur at runtime.
class FromMaster(msg):
    fmt = 'iii'
    def __init__(self):
        super().__init__(FromMaster, ToMaster)
        self.i0 = 0
        self.i1 = 0
        self.i2 = 0

    def pack(self):
        self.mvbuf[:] = ustruct.pack(self.fmt, self.i0, self.i1, self.i2)
        return self.buf

    def unpack(self):
        self.i0, self.i1, self.i2 = ustruct.unpack(self.fmt, self.buf)
        return self

class ToMaster(msg):
    fmt = 'iii'
    def __init__(self):
        super().__init__(FromMaster, ToMaster)
        self.i0 = 0
        self.i1 = 0
        self.i2 = 0

    def pack(self):
        self.mvbuf[:] = ustruct.pack(self.fmt, self.i0, self.i1, self.i2)
        return self.buf

    def unpack(self):
        self.i0, self.i1, self.i2 = ustruct.unpack(self.fmt, self.buf)
        return self
