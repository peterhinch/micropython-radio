# Generic Tests for radio-fast module.
# Modify config.py to provide master_config and slave_config for your hardware.
import pyb, radio_fast
from config import master_config, slave_config, FromMaster, ToMaster

def test_master():
    m = radio_fast.Master(master_config)
    send_msg = FromMaster()
    while True:
        result = m.exchange(send_msg)
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        send_msg.i0 += 1
        pyb.delay(1000)

def test_slave():
    s = radio_fast.Slave(slave_config)
    send_msg = ToMaster()
    while True:
        result = s.exchange(send_msg)       # Wait for master
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        send_msg.i0 += 1
