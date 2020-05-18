# nbtest.py Test nonblocking read on slave.

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

# Requires uasyncio V3 and as_drivers directory (plus contents) from
# https://github.com/peterhinch/micropython-async/tree/master/v3

from time import ticks_ms, ticks_diff
import uasyncio as asyncio
from as_drivers.hd44780.alcd import LCD, PINLIST  # Library supporting Hitachi LCD module
import radio_fast as rf
from config import FromMaster, ToMaster, testbox_config, v2_config  # Configs for my hardware

st = '''
On slave (with LCD) issue nbtest.test(False)
On master issue nbtest.test()
'''

print(st)

async def run_master():
    m = rf.Master(v2_config)  # Master runs on V2 PCB with SD card
    send_msg = FromMaster()
    while True:
        result = m.exchange(send_msg)
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        send_msg.i0 += 1
        await asyncio.sleep(1)

async def slave(lcd):
    await asyncio.sleep(0)
    s = rf.Slave(testbox_config)  # Slave on testbox
    send_msg = ToMaster()
    while True:
        start = ticks_ms()
        result = None
        while not s.any():  # Wait for master to send
            await asyncio.sleep(0)
            t = ticks_diff(ticks_ms(), start)
            if t > 4000:
                break
        else:  # Master has sent
            start = ticks_ms()
            result = s.exchange(send_msg)
            t = ticks_diff(ticks_ms(), start)
        if result is None:
            lcd[0] = 'Timeout'
        elif result:
            lcd[0] = str(result.i0)
        lcd[1] = 't = {}mS'.format(t)
        await asyncio.sleep(0)
        send_msg.i0 += 1

def test(master=True):
    lcd = LCD(PINLIST, cols = 24)
    try:
        asyncio.run(run_master() if master else slave(lcd))
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
