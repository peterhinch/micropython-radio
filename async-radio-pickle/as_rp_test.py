# as_rp_test.py Test/demo programs for async_radio_pickle.py


import uasyncio as asyncio
import async_radio_pickle as rp
import pyb
from myconfig import *  # Configs for my hardware


# Generator returns changing test data to transmit
def make_data_xxxx():
    obj = [0, '']
    x = ord('a')
    while True:
        yield obj
        obj[0] += 1
        obj[1] += chr(x)
        x = x +1 if x < ord('z') else ord('a')
        if len(obj[1]) > 12:
            obj[1] = ''         # Fit in LCD

def make_data():  # try no strings for reliability
    obj = [0, 0]
    while True:
        yield obj
        obj[0] += 1
        obj[1] = pyb.rng()


async def test_channel(config, master):
    chan = rp.Channel(config, master, rxcb = lambda data: print(data),
                        statecb = lambda state: print('Link state', state))
    md = make_data()
    arbitrary_object = next(md)
    while True:
        await asyncio.sleep_ms(7000)
        if chan.send(arbitrary_object):
            arbitrary_object = next(md)

# Run this on one end of the link
def tm():
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(config_v1, 1))
    loop.run_forever()

# And this on the other
def ts():
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(config_v2, 0))
    loop.run_forever()

