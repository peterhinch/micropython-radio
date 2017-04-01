# as_rp_test.py Test/demo programs for asynchronous version of radio_pickle.py 


import uasyncio as asyncio
import async_radio_pickle as rp
import pyb
from myconfig import *  # Configs for my hardware

# Simple confidence checks/demo
async def st_master():  # Test master on V1 PCB.
    m = rp.Master(config_v1)
    obj = [0, '']
    x = ord('a')
    while True:
        try:
            result = await m.exchange(obj)
        except OSError:  # Optionally trap timeout errors (e.g. out of range)
            print("Timeout")
        else:
            print(result)
        pyb.delay(1000)
        obj[0] += 1

async def st_slave():  # Test slave: runs on V2 PCB
    s = rp.Slave(config_v2)
    obj = [0, '']
    x = ord('a')
    while True:
        try:
            result = await s.exchange(obj)
        except rp.NoData:  # Master has sent nothing
            pass
        except OSError:
            print("Timeout")
        else:
            print(result)
            obj[0] += 1
            obj[1] += chr(x)
            x = x +1 if x < ord('z') else ord('a')
            if len(obj[1]) > 12:
                obj[1] = ''         # Fit in LCD



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

async def test_channel(master):
    if master:
        chan = rp.Channel(config_v1, True, rxcb = lambda data: print(data),
                          statecb = lambda state: print('Link state', state))
    else:
        chan = rp.Channel(config_v2, False, rxcb = lambda data: print(data),
                          statecb = lambda state: print('Link state', state))
    md = make_data()
    arbitrary_object = next(md)
    while True:
        await asyncio.sleep_ms(1500)
        if chan.send(arbitrary_object):
            arbitrary_object = next(md)

def tm():
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(1)) # Schedule ASAP
    loop.run_forever()

def ts():
    loop = asyncio.get_event_loop()
    loop.create_task(test_channel(0)) # Schedule ASAP
    loop.run_forever()

