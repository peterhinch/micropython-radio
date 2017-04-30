# as_rp_test.py Test/demo programs for async_radio_pickle.py

import uasyncio as asyncio
import async_radio_pickle as rp
import pyb
from myconfig import *  # Configs for my hardware

green_led = pyb.LED(2)
red_led = pyb.LED(1)

# Generator returns changing test data to transmit
def make_ascii():
    obj = [0, '']
    x = ord('a')
    while True:
        yield obj
        obj[0] += 1
        obj[1] += chr(x)
        x = x +1 if x < ord('z') else ord('a')
        if len(obj[1]) > 100: # 12:
            obj[1] = ''         # Fit in LCD

# This version creates short integers
def make_data():
    obj = [0, 0]
    while True:
        yield obj
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
def cb_rx(data):
    global last_num, missing, dupe, rx_started
    num = data[0]  # Incrementing recieved message no.
    rx_started = True
    if started and num != last_num + 1:
        if num == last_num:
            dupe += 1
        elif num > last_num + 1:
            raise OSError('Missing record') # TEST
            missing += 1
    last_num = num
    print(data)

async def report(channel):  # DEBUG
    global started
    while not rx_started:
        await asyncio.sleep(1)
    await asyncio.sleep(30)
    print('Start recording statistics')
    started = True
    while True:
        print('Fail count: {} dupes: {} missing: {}'.format(channel._radio.failcount, dupe, missing))
        await asyncio.sleep(60)

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

# Run this on one end of the link
def tm(test=0):
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(config_v1, test, True))
    loop.run_forever()

# And this on the other
def ts(test=0):
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(config_v2, test, False))
    loop.run_forever()
