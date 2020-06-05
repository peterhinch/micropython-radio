# as_nrf_test.py Test script for as_nrf_stream

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
        def __init__(self, _):
            self.on = lambda : None
            self.off = lambda : None

led = LED(1)  # Red lit during an outage.
missed = 0  # Non-sequential records
outages = 0
tstart = 0

# Generator produces variable length strings: test for issues mapping onto
# nRF24l01 fixed size 32 byte records.
def gen_str(maxlen=65):
    while True:
        s = ''
        x = ord('a')
        while len(s) < maxlen:
            s += chr(x)
            yield s
            x = x + 1 if x < ord('z') else ord('a')

async def sender(device, interval):
    gs = gen_str()
    ds = [0, 0, [], '']  # Data object for transmission
    swriter = asyncio.StreamWriter(device, {})
    while True:
        s = ''.join((ujson.dumps(ds), '\n'))
        swriter.write(s.encode())  # convert to bytes
        await swriter.drain()
        await asyncio.sleep_ms(interval)
        ds[0] += 1  # Record number
        ds[1] = missed  # Send local missed record count to remote
        ds[2] = device.stats()
        ds[3] = next(gs)  # Range of possible string lengths

async def receiver(device):
    global missed
    msg = 'Missed record count: {:3d} (local) {:3d} (remote).'
    tmsg = 'Uptime: {:7.2f}hrs Outages: {:3d}'
    smsg = '{} statistics. Timeouts: RX {} TX {} Received packets: All {} Non-duplicate data {}'
    sreader = asyncio.StreamReader(device)
    x = 0
    last = None  # Record no. of last received data
    while True:
        res = await sreader.readline()  # Can return b''
        if res:
            # If res was corrupt ujson.loads would throw ValueError. In practise
            try:
                dat = ujson.loads(res)  # the protocol prevents this.
            except ValueError:
                print('JSON error', res)
                raise
            print('Received record no: {:5d} text: {:s}'.format(dat[0], dat[3]))
            if last is not None and (last + 1) != dat[0]:
                missed += 1
            last = dat[0]
            x += 1
            x %= 20
            if not x:
                print(msg.format(missed, dat[1]))
                print(tmsg.format((time.time() - tstart)/3600, outages))
                if isinstance(dat[2], list):
                    print(smsg.format('Remote', *dat[2]))
                local_stats = device.stats()
                if isinstance(local_stats, list):
                    print(smsg.format('Local', *local_stats))

async def fail_detect(device):
    global outages
    while True:
        if device.t_last_ms() > 5000:
            outages += 1
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
    # But script uses different periods test for timing issues:
    asyncio.create_task(sender(device, 2000 if master else 1777))
    asyncio.create_task(receiver(device))
    await fail_detect(device)

def test(master):
    try:
        asyncio.run(main(master))
    finally:  # Reset uasyncio case of KeyboardInterrupt
        asyncio.new_event_loop()

msg = '''Test script for as_nrf_stream driver for nRF24l01 radios.
On master issue
as_nrf_test.test(True)
On slave issue
as_nrf_test.test(False)
'''
print(msg)
