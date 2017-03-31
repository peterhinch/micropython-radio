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

def tm():
    loop = asyncio.get_event_loop()
    loop.create_task(st_master()) # Schedule ASAP
    loop.run_forever()

def ts():
    loop = asyncio.get_event_loop()
    loop.create_task(st_slave()) # Schedule ASAP
    loop.run_forever()

# *********** FULL TEST ***********
# These tests run a range of packet sizes. Because they iterate over different lengths, if
# run for 1.5 hours a wide range of asymmetrical packet sizes are tested. The receiver
# sends back the length of the string received. If this doesn't match what was sent, the
# test quits.
async def at_slave():
    s = rp.Slave(config_slave)
    obj = [0, ''] # This is the object to be sent
    x = ord('a')
    while True:
        try:
            result = s.exchange(obj)
        except rp.NoData:
            pass # Master has sent no data. Try again.
        except OSError: # Optionally trap timeout errors (e.g. out of range)
            print("Timeout")
        else:
            print(result) # Print the received object
            if result[0] != len(result[1]):
                print('Error')
                break
            obj[1] = obj[1] + chr(x) if len(obj[1]) < 70 else '' # Keep from getting too huge
            x = x +1 if x < ord('z') else ord('a') 
            obj[0] = len(obj[1])

async def at_master():
    m = rp.Master(config_master)
    obj = [0, ''] # object to be sent
    x = ord('a')
    while True:
        try:
            result = m.exchange(obj)
        except OSError:  # Optionally trap timeout errors (e.g. out of range)
            print("Timeout")
        else:
            print(result)  # No errors raised
            if result[0] != len(result[1]):
                print('Error')
                break
        pyb.delay(1000)  # send 1 message per sec
        obj[1] = obj[1] + chr(x) if len(obj[1]) < 71 else ''  # Keep from getting too huge
        x = x +1 if x < ord('z') else ord('a') 
        obj[0] = len(obj[1])

def test_master():
    loop = asyncio.get_event_loop()
    loop.create_task(at_master()) # Schedule ASAP
    loop.run_forever()

def test_slave():
    loop = asyncio.get_event_loop()
    loop.create_task(at_slave()) # Schedule ASAP
    loop.run_forever()

