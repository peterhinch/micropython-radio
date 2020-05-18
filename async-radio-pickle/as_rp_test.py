# as_rp_test.py Test/demo programs for async_radio_pickle.py

import uasyncio as asyncio
import async_radio_pickle as rp
import pyb
import gc
import micropython  # Test for string interning issue #2280
from myconfig import *  # Configs for my hardware

red_led = pyb.LED(1)
green_led = pyb.LED(2)
yellow_led = pyb.LED(3)
MAXLEN = 100  # Max string length (12 fits LCD)
# Generator returns changing test data to transmit
def make_ascii():
    obj = [0, '']
    x = ord('a')
    while True:
        yield obj[:]
        obj[0] += 1
        obj[1] += chr(x)
        x = x +1 if x < ord('z') else ord('a')
        if len(obj[1]) > MAXLEN:
            obj[1] = ''

# This version creates short integers
def make_data():
    obj = [0, 0]
    while True:
        yield obj[:]  # Must create copy
        obj[0] += 1
        obj[1] = pyb.rng()

async def heartbeat():
    while True:
        red_led.toggle()
        await asyncio.sleep_ms(500)

# Reflect link state on green LED
def cb_state(state):
    if state:
        green_led.on()
    else:
        green_led.off()

# Callback for received data
last_num = 0
missing = 0
dupe = 0
rx_started = False
started = False
strlen = 0
strfail = 0
def cb_rx(data):
    global last_num, missing, dupe, rx_started, strlen, strfail
    print(data)
    yellow_led.toggle()
    num = data[0]  # Incrementing recieved message no.
    rx_started = True
    if started and num != last_num + 1:
        if num == last_num:
            dupe += 1
        elif num > last_num + 1:
            raise OSError('Missing record')
            missing += 1
    s = data[1]
    if isinstance(s, str) or isinstance(s, bytes):
        if started and not num == last_num: # ignore dupes
            if len(s) != (strlen + 1) % (MAXLEN + 1): # error
                strfail += 1
        strlen = len(s)
    last_num = num

async def report(channel):  # DEBUG
    global started
    while not rx_started:
        await asyncio.sleep(1)
    await asyncio.sleep(30)
    print('Start recording statistics')
    started = True
    fs = '************** Fail count: {} dupes: {} missing: {} wrong length: {}'
    while True:
        print(fs.format(channel._radio.failcount, dupe, missing, strfail))
        await asyncio.sleep(60)
        gc.collect()
        micropython.mem_info()

async def test_channel(config, test, master):
    chan = rp.Channel(config, master, rxcb = cb_rx, statecb = cb_state)
    loop = asyncio.get_event_loop()
    loop.create_task(heartbeat())
    loop.create_task(report(chan))
    md = make_data() if test == 0 else make_ascii()
    arbitrary_object = next(md)
    t = 3000 if master else 2534  # Test no synch between master and slave
    while True:
        await asyncio.sleep_ms(t)
        if chan.send(arbitrary_object):
            arbitrary_object = next(md)

st = '''
On testbox run as_rp_test.tm()
On V2 board (with SD slot) run as_rp_test.ts()
'''
print(st)  # Notes for my hardware

# Run this on one end of the link
def tm(test=0):
    try:
        asyncio.run(test_channel(config_testbox, test, True))
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()

# And this on the other
def ts(test=0):
    try:
        asyncio.run(test_channel(config_v2, test, False))
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
