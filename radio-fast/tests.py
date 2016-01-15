# Generic Tests for radio-fast module.
# Modify config.py to provide master_config and slave_config for your hardware.
import pyb
import radio_fast as rf
from config import master_config, slave_config

messages = rf.MessagePair()                     # Instantiate messages and check compatibility

def tm():
    m = rf.Master(master_config, messages)
    while True:
        result = m.exchange()
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        messages.from_master.i0 += 1
        pyb.delay(1000)

def ts():
    s = rf.Slave(slave_config, messages)
    while True:
        result = s.exchange(block = True)       # Wait for master
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        messages.to_master.i0 += 1
