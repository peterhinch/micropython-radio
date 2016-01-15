# Test nonblocking read on slave.
# usched and lcdthread at https://github.com/peterhinch/Micropython-scheduler.git

import pyb
import radio_fast as rf
from usched import Sched, wait, Roundrobin
from lcdthread import LCD, PINLIST              # Library supporting Hitachi LCD module
from config import testbox_config, v1_config    # Configs for my hardware

messages = rf.MessagePair()                     # Instantiate messages and check compatibility

def tm():
    m = rf.Master(v1_config, messages)          # Master runs on V1 PCB
    while True:
        result = m.exchange()
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        messages.from_master.i0 += 1
        pyb.delay(1000)

def slave(lcd):
    yield Roundrobin()
    s = rf.Slave(testbox_config, messages)      # Slave on testbox
    while True:
        while True:
            start = pyb.millis()
            result = s.exchange(block = False)
            t = pyb.elapsed_millis(start)
            yield Roundrobin()
            if result is None:                  # Timeout
                break
            if result:                          # Success
                break
        if result is None:
            lcd[0] = 'Timeout'
        elif result:
            lcd[0] = str(result.i0)
        lcd[1] = 't = {}mS'.format(t)
        yield Roundrobin()
        messages.to_master.i0 += 1

# Run this on testbox, run tm() on master
def test():
    objSched = Sched()
    lcd0 = LCD(PINLIST, objSched, cols = 24)
    objSched.add_thread(slave(lcd = lcd0))
    objSched.run()
