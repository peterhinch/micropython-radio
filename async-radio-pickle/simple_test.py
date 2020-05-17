# simple_test.py Test/demo programs for async_radio_pickle.py

import uasyncio as asyncio
import async_radio_pickle as rp
import pyb
from myconfig import *  # Hardware configs. Edit this file!

red_led = pyb.LED(1)
green_led = pyb.LED(2)
yellow_led = pyb.LED(3)

# Generator creates short integers
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
def cb_rx(data):
    print(data)
    yellow_led.toggle()


async def test_channel(config, master):
    chan = rp.Channel(config, master, rxcb = cb_rx, statecb = cb_state)
    loop = asyncio.get_event_loop()
    loop.create_task(heartbeat())
    md = make_data()  # Instantiate generator
    arbitrary_object = next(md)
    t = 3000 if master else 2534  # Test no synch between master and slave
    while True:
        await asyncio.sleep_ms(t)
        if chan.send(arbitrary_object):
            arbitrary_object = next(md)

# Run this on one end of the link
def tm(test=0):
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(config_testbox, True))  # EDIT THIS (config)
    loop.run_forever()

# And this on the other
def ts(test=0):
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(config_v2, False))  # EDIT THIS (config)
    loop.run_forever()
