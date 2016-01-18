# msg.py Message base class for radio-fast protocol

import ustruct

class RadioConfig(object):                      # Configuration for an nRF24L01 radio
    channel = 99                                # Necessarily shared by master and slave instances.
    def __init__(self, *, spi_no, csn_pin, ce_pin):# May differ between instances
        self.spi_no = spi_no
        self.ce_pin = ce_pin
        self.csn_pin = csn_pin

# Message base class.
class msg(object):
    errmsg = 'config.py: ToMaster and FromMaster messages have mismatched payload sizes/formats'
    def __init__(self, cls1, cls2):
        self.buf = bytearray(cls1.payload_size())
        self.mvbuf = memoryview(self.buf)
        assert cls1.payload_size() == cls2.payload_size(), self.errmsg

    def store(self, data):
        self.mvbuf[:] = data

    @classmethod
    def payload_size(cls):
        return ustruct.calcsize(cls.fmt)        # Size of subclass packed data
