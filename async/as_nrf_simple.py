# as_nrf_simple.py Test script for as_nrf_stream

# (C) Peter Hinch 2020
# Released under the MIT licence

import uasyncio as asyncio
from as_nrf_stream import Master, Slave
from asconfig import config_master, config_slave  # Hardware configuration


async def sender(device):
    swriter = asyncio.StreamWriter(device, {})
    while True:
        swriter.write(b'Hello receiver\n')  # Must be bytes
        await swriter.drain()
        await asyncio.sleep(1)

async def receiver(device):
    sreader = asyncio.StreamReader(device)
    while True:
        res = await sreader.readline()
        if res:  # Can return b''
            print('Received:', res)

async def main(master):
    device = Master(config_master) if master else Slave(config_slave)
    asyncio.create_task(receiver(device))
    await sender(device)

def test(master):
    try:
        asyncio.run(main(master))
    finally:  # Reset uasyncio case of KeyboardInterrupt
        asyncio.new_event_loop()

msg = '''Test script for as_nrf_stream driver for nRF24l01 radios.
On master issue
as_nrf_simple.test(True)
On slave issue
as_nrf_simple.test(False)
'''
print(msg)
