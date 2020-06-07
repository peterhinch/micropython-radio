# as_nrf_json.py Test script for as_nrf_stream

# (C) Peter Hinch 2020
# Released under the MIT licence

import uasyncio as asyncio
import ujson
import time
from as_nrf_stream import Master, Slave
from asconfig import config_master, config_slave  # Hardware configuration

try:
    from pyb import LED
except ImportError:  # Non-pyboard platform: dummy LED
    class LED:
        on = lambda _ : None
        off = lambda _ : None
        toggle = lambda _ : None

led = LED(1)  # Red lit during an outage.
green = LED(2)  # Message received

async def sender(device):
    ds = [0, 0]  # Data object for transmission
    swriter = asyncio.StreamWriter(device, {})
    while True:
        s = ''.join((ujson.dumps(ds), '\n'))
        swriter.write(s.encode())  # convert to bytes
        await swriter.drain()
        await asyncio.sleep(2)
        ds[0] += 1  # Record number
        ds[1] = device.t_last_ms()

async def receiver(device):
    sreader = asyncio.StreamReader(device)
    while True:
        res = await sreader.readline()  # Can return b''
        if res:
            green.toggle()
            try:
                dat = ujson.loads(res)
            except ValueError:  # Extremely rare case of data corruption. See docs.
                pass
            else:
                print('Received values: {:5d} {:5d}'.format(*dat))

async def fail_detect(device):
    while True:
        if device.t_last_ms() > 5000:
            print('Remote outage')
            led.on()
            while device.t_last_ms() > 5000:
                await asyncio.sleep(1)
            print('Remote has reconnected')
            led.off()
        await asyncio.sleep(1)


async def main(master):
    global tstart
    tstart = time.time()
    # This line is the only *necessary* diffference between master and slave:
    device = Master(config_master) if master else Slave(config_slave)
    asyncio.create_task(sender(device))
    asyncio.create_task(receiver(device))
    await fail_detect(device)

def test(master):
    try:
        asyncio.run(main(master))
    finally:  # Reset uasyncio case of KeyboardInterrupt
        asyncio.new_event_loop()

msg = '''Test script for as_nrf_stream driver for nRF24l01 radios.
On master issue
as_nrf_json.test(True)
On slave issue
as_nrf_json.test(False)
'''
print(msg)
