# Tests for radio-fast module.
# usched and lcdthread at https://github.com/peterhinch/Micropython-scheduler.git

import pyb
import radio_fast as rf
from usched import Sched, wait, Roundrobin
from lcdthread import LCD, PINLIST              # Library supporting Hitachi LCD module
from config import FromMaster, ToMaster, testbox_config, v1_config  # Configs for my hardware


def tm():
    m = rf.Master(testbox_config)
    send_msg = FromMaster()
    while True:
        result = m.exchange(send_msg)
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        send_msg.i0 += 1
        pyb.delay(1000)

def ts():
    from micropower import PowerController
    power_controller = PowerController(pin_active_high = 'Y12', pin_active_low = 'Y11')
    power_controller.power_up()
    s = rf.Slave(v1_config)
    send_msg = ToMaster()
    while True:
        result = s.exchange(send_msg)       # Wait for master
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        send_msg.i0 += 1

def master(lcd):
    yield Roundrobin()
    m = rf.Master(testbox_config)
    send_msg = FromMaster()
    while True:
        start = pyb.millis()
        result = m.exchange(send_msg)
        t = pyb.elapsed_millis(start)
        lcd[1] = 't = {}mS'.format(t)
        if result is not None:
            lcd[0] = str(result.i0)
        else:
            lcd[0] = 'Timeout'
        yield from wait(1.0)
        send_msg.i0 += 1

# Run this on testbox, run ts() on slave
def test():
    objSched = Sched()
    lcd0 = LCD(PINLIST, objSched, cols = 24)
    objSched.add_thread(master(lcd = lcd0))
    objSched.run()
