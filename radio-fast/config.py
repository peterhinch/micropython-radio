# Modify this
import ustruct

class RadioConfig(object):                      # Configuration for an nRF24L01 radio
    channel = 99                                # Necessarily shared by both instances. Modify as required.
    def __init__(self, *, spi_no, csn_pin, ce_pin):# May differ
        self.spi_no = spi_no
        self.ce_pin = ce_pin
        self.csn_pin = csn_pin

# Modify for your hardware
testbox_config = RadioConfig(spi_no = 1, csn_pin = 'X5', ce_pin = 'Y11') # My testbox
v1_config = RadioConfig(spi_no = 1, csn_pin = 'X5', ce_pin = 'X4')   # V1 Micropower PCB
# config_v2 = RadioConfig(spi_no = 1, csn_pin = 'X5', ce_pin = 'X2')    # V2 Micropower PCB

class msg(object):
    def __init__(self, fmt):
        self.payload_size = ustruct.calcsize(fmt)
        self.buf = bytearray(self.payload_size)

    def store(self, data):
        if len(data) == self.payload_size:
            self.buf[0 : self.payload_size] = data
        else:
            raise OSError

# For both messages need to alter fmt, instance variables, pack() and unpack() methods, to suit application.
# Both messages must pack to the same length otherwise an assertion failure will occur at runtime.
class FromMaster(msg):
    fmt = 'iii'
    def __init__(self):
        super().__init__(self.fmt)
        self.i0 = 0
        self.i1 = 0
        self.i2 = 0

    def pack(self):
        self.buf[0 : self.payload_size] = ustruct.pack(self.fmt, self.i0, self.i1, self.i2)
        return self.buf

    def unpack(self):
        self.i0, self.i1, self.i2 = ustruct.unpack(self.fmt, self.buf)
        return self

class ToMaster(msg):
    fmt = 'iii'
    def __init__(self):
        super().__init__(self.fmt)
        self.i0 = 0
        self.i1 = 0
        self.i2 = 0

    def pack(self):
        self.buf[0 : self.payload_size] = ustruct.pack(self.fmt, self.i0, self.i1, self.i2)
        return self.buf

    def unpack(self):
        self.i0, self.i1, self.i2 = ustruct.unpack(self.fmt, self.buf)
        return self
