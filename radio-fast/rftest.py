# Tests for radio-fast module.

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

# Requires uasyncio V3 and as_drivers directory (plus contents) from
# https://github.com/peterhinch/micropython-async/tree/master/v3

from time import ticks_ms, ticks_diff
import uasyncio as asyncio
import radio_fast as rf
from as_drivers.hd44780.alcd import LCD, PINLIST  # Library supporting Hitachi LCD module
from config import FromMaster, ToMaster, testbox_config, v2_config  # Configs for my hardware

st = '''
On master (with LCD) issue rftest.test()
On slave issue rftest.test(False)
'''

print(st)

#async def tm():
    #m = rf.Master(testbox_config)
    #send_msg = FromMaster()
    #while True:
        #result = m.exchange(send_msg)
        #if result is not None:
            #print(result.i0)
        #else:
            #print('Timeout')
        #send_msg.i0 += 1
        #asyncio.sleep(1)

async def slave():
    # power control done in main.py
    s = rf.Slave(v2_config)  # Slave runs on V2 PCB (with SD card)
    send_msg = ToMaster()
    while True:
        await asyncio.sleep(0)
        result = s.exchange(send_msg)       # Wait for master
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        send_msg.i0 += 1

async def run_master(lcd):
    await asyncio.sleep(0)
    m = rf.Master(testbox_config)
    send_msg = FromMaster()
    while True:
        start = ticks_ms()
        result = m.exchange(send_msg)
        t = ticks_diff(ticks_ms(), start)
        lcd[1] = 't = {}mS'.format(t)
        if result is not None:
            lcd[0] = str(result.i0)
        else:
            lcd[0] = 'Timeout'
        await asyncio.sleep(1)
        send_msg.i0 += 1

def test(master=True):
    lcd = LCD(PINLIST, cols = 24)
    try:
        asyncio.run(run_master(lcd) if master else slave())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
