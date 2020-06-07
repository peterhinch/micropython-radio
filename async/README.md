# 1. nRF24l01 Stream driver

This enables a pair of nRF24l01 radios to provide a link that implements the
MicroPython `uasyncio` I/O interface. The object is to enable a pair of radios
to have the same asynchronous interface as a pair of UARTs or sockets.

Users may choose a serialisation library to exchange Python objects.
Alternatively an application may simply exchange fixed or variable length
`bytes` instances. Demo scripts illustrate both approaches including the use of
`ujson` for Python object interchange.

## 1.1. Overview

Radio links are inherently unreliable, not least since receiver and transmitter
may move out of range. The link may also be disrupted by radio frequency
interference. This driver mitigates this by ensuring that, in the event of a
link outage, data transfer will resume without loss when connectivity is
restored.

The use of stream I/O means that the interface matches that of objects such as
sockets and UARTs. The objects exchanged are `bytes` instances.

Where an application uses a serialisation library like `pickle` or `ujson`, the
resultant `bytes` objects will be of variable length. This raises the issue of
how the recipient determines the end of a message. The simplest approach is for
the application to terminate the `bytes` with  a newline character (`b'\n'`).
This allows the recipient to use the `StreamReader.readline` method.

In this doc an application-level `bytes` object is termed a `message` as
distinct from a `packet` which is the fixed length `bytes` object exchanged by
the radios.

The underlying protocol's API hides the following details:
 * The fact that the radio hardware is half-duplex.
 * The hardware limit on message length.
 * The asymmetrical master/slave design of the underlying protocol.

It provides a symmetrical full-duplex interface: either node can send a
`message` at any time. The cost is some loss in throughput and increase in
latency relative to the `radio-fast` module.

# 2. Dependencies

The library requires the
[official nRF24l01 driver](https://github.com/micropython/micropython/blob/master/drivers/nrf24l01/nrf24l01.py)
which should be copied to both targets' filesystems. It requires `uasyncio`
version 3. This is built in to daily builds of firmware and will be available
in official releases beginning with V1.13.

# 3. Files and installation

 1. `as_nrf_stream.py` The library.
 2. `asconfig.py` User-definable hardware configuration for the radios.
 3. `as_nrf_simple.py` Minimal demo of exchanging `bytes` objects.
 4. `as_nrf_json.py` Demo of exchanging Python objects and detecting outages.
 5. `as_nrf_test.py` Test script. This transmits and reports statistics showing
 link characteristics.

To install, adapt `asconfig.py` to match your hardware. Copy it and
`as_nrf_stream` to both targets. Ensure dependencies are satisfied. Copy any of
the above test scripts to both targets. Test scripts print running instructions
on import.

# 4. Usage examples

## 4.1 Exchanging bytes objects

Taken from `as_nrf_simple.py`. This is run by issuing
```python
as_nrf_simple.test(True)
```
on the master, and the same with arg `False` on the slave. Note `asconfig.py`
must be adapted for your hardware and deployed to both nodes.
```python
import uasyncio as asyncio
from as_nrf_stream import Master, Slave
from asconfig import config_master, config_slave  # Hardware configuration

async def sender(device):
    swriter = asyncio.StreamWriter(device, {})
    while True:
        swriter.write(b'Hello receiver\n')  # Must be bytes, newline terminated
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
```
Note that the radios could be replaced by a UART by changing initialisation
only. The `sender` and `receiver` coroutines would be identical.

## 4.2 Exchanging Python objects

In this example a list is passed. Any object supported by ujson may be used.
```python
import uasyncio as asyncio
import ujson
from as_nrf_stream import Master, Slave
from asconfig import config_master, config_slave  # Hardware configuration

async def sender(device):
    ds = [0, 0]  # Data object for transmission
    swriter = asyncio.StreamWriter(device, {})
    while True:
        s = ''.join((ujson.dumps(ds), '\n'))
        swriter.write(s.encode())  # convert to bytes
        await swriter.drain()
        await asyncio.sleep(1)
        ds[0] += 1  # Record number

async def receiver(device):
    sreader = asyncio.StreamReader(device)
    while True:
        res = await sreader.readline()  # Can return b''
        if res:
            try:
                dat = ujson.loads(res)
            except ValueError:  # Extremely rare. See section 10.1
                pass
            else:
                print(dat)

async def main(master):
    device = Master(config_master) if master else Slave(config_slave)
    asyncio.create_task(receiver(device))
    await sender(device)

def test(master):
    try:
        asyncio.run(main(master))
    finally:  # Reset uasyncio case of KeyboardInterrupt
        asyncio.new_event_loop()
```

# 5. Configuration: asconfig.py

This file is intended for user adaptation and contains configuration details
for the two radios.  It is intended that a common `asconfig.py` is deployed to
both nodes.

Node hardware may or may not be identical: the two nodes may use different pin
numbers or SPI bus numbers. The `RadioSetup` class uses instance variables for
values which may differ between nodes and class variables for those which must
be common to both.

## 5.1 Class RadioSetup

This is intended to facilitate sharing a configuration between master and slave
devices to reduce the risk of misconfiguration. A `RadioSetup` object may be
instantiated and configured in a module common to master and slave. An example
may be found in `asconfig.py`.

#### Class variables (shared by both nodes)

 * `tx_ms = 200` Defines the maximum time a transmitter will wait for a successful
 data transfer.  
 * `channel` Defines the radios' carrier frequency. See
 [section 7](./README.md#7-radio-channels).

#### Constructor (args may differ between nodes)

This takes the following arguments being objects instantiated by the `machine`
module:
 * `spi` An SPI bus instance.  
 * `csn` Pin instance connected to CSN.  
 * `ce` Pin instance linked to CE.  
 * `stats=False` If `True` the driver gathers statistics including a count of
 transmit and receive timeouts. These can be used to glean a rough measure of
 link quality. See `as_nrf_test.py` for an example of displaying these. If
 `False` a (tiny) amount of RAM is saved. See
 [section 8](./README.md#8-statistics).

# 6. API: as_nrf_stream

The library provides two classes, `Master` and `Slave`. The device at one end
of the link must be instantiated as `Master`, the other as `Slave`. Their user
interfaces are identical. At application level it does not matter which is
chosen for a given purpose as the API is provided by a common base class. The
following applies to both classes.

#### Constructor

This takes a single argument, being an instance of the `RadioSetup` class as
described above.

#### Methods

 * `t_last_ms` No args. Return value: the time in ms since the last packet was
 received. May be used to detect outages. See `as_nrf_test.py` for an example.
 * `stats` If specified in the config file, performance counters are maintained
 in a list of integers. This method returns that list, or `None` if the config
 has disabled statistics. See [section 8](./README.md#8-statistics).

#### Typical sender coroutine

This instantiates a `StreamWriter` from a `Master` or `Slave` instance and
writes `bytes` objects to it as required. If the reader is to use `.readline`
these should be newline terminated. The `drain` method queues the bytes for
transmission. If transmission of the previous call to `drain` has completed,
return will be "immediate"; otherwise the coroutine will pause until
transmission is complete and reception has been acknowledged. In the event of
an outage, the pause duration will be that of the outage.
```python`
async def sender(device):
    swriter = asyncio.StreamWriter(device, {})
    while True:
        swriter.write(b'Hello receiver\n')  # Must be bytes. Newline terminated
        await swriter.drain()  # May pause until received.
        await asyncio.sleep(1)
```

#### Typical receiver coroutine

This instantiates a `StreamReader` from a `Master` or `Slave` instance and
waits until a complete line is received.
```python
async def receiver(device):
    sreader = asyncio.StreamReader(device)
    while True:
        res = await sreader.readline()
        if res:   # Can return b''
            print('Received:', res)
```
In order to keep data interchange running fast and efficiently, applications
should run a coroutine which spends most of its time in `.readline`. Where slow
operations are needed to process incoming data, these should be delegated to
other concurrent tasks.

The `.readline` method has two possible return values: a single complete line
or an empty `bytes` instance. Applications should check for and ignore the
latter.

# 7. Radio channels

The RF frequency is determined by the `RadioSetup` instance as described above.
The `channel` value maps onto frequency by means of the following formula:  
freq = 2400 + channel [MHz]  
The maximum channel no. is 125. The ISM (Industrial, Scientific and Medical)
band covers 2400-2500MHz and is licensed for use in most jurisdictions. It is,
however, shared with many other devices including WiFi, Bluetooth and microwave
ovens. WiFi and Bluetooth generally cut off at 2.4835GHz so channels 85-99
should avoid the risk mutual interference. Note that frquencies of 2.5GHz and
above are not generally licensed for use: check local regulations before using
these devices.

# 8. Statistics

These monitor the internal behaviour of the driver and may be used as a crude
measure of link quality. If enabled in the config the device's `stats` method
returns a list of four integers. These are counters initialised to zero and
incrementing when a given event occurs. Their meaning (by offset) is:
 0. Receive timeouts. Relevant only to `Master`: increments when the slave does
 not respond in 1.5* `tx_ms` [section 5.1](./README.md#51-radio-setup). These
 will repeatedly occur during an outage.
 1. Transmit timeouts. Counts instances where transmit fails to complete in
 `tx_ms`. In my testing this rarely occurs, and only during an outage.
 2. Received data packets. Counts all packets received with a data payload.
 3. Received non-duplicate data packets.

The driver handles a stream and has no knowledge of application-level record
structure. Received data statistics refer to packets. In general the mapping of
records onto packets is one-to-many. Further, if a node has nothing to send, it
sends a packet with no payload.

Ways of using these statistics to gauge link quality are to measure the rate at
which receive timeouts occur on the `Master` or to measure the rate at which
duplicate packets are received - along lines of  
`(stats[2] - stats[3)/seconds`.

Receive timeouts occur on `Master` only if `Master` detects no response from
`Slave` in a period of just over 1.5*`tx_ms`. These may occur because the slave
did not receive the packet from `Master`, or because `Master` did not receive
the response from `Slave`.

Duplicate packets occur when one node fails to receive a transmission from the
other. In this event it keeps trying to send the same packet until a response
is detected (the driver detects and discards dupes).

# 9. Protocol

The underlying communications channel is unreliable inasmuch as transmitted
packets may not be received. However, if a packet is received, the radio
hardware aims to guarantee that its contents are correct. In practice this
"guarantee" is not perfect: see [section 10](./README.md#101-message-integrity).

The protocol has two aspects: management of send/receive and management of
packets. There is no point in a node transmitting if its peer is not listening.
Any packet sent may be lost: this needs to be detected and rectified.

## 9.1 Packets

Packets comprise 32 bytes. Byte 0 is a command, byte 1 is the payload length.
The remaining bytes are the payload padded with 0. The payload may be empty,
the length byte then being 0. Packets carrying a payload are known as payload
packets (PP).

There are two commands: `MSG` and `ACK`. Only `Master` sends the `ACK` command.
`MSG` denotes a normal packet, `ACK` signifies acknowledgement of a PP from
`Slave`. Both packet types may or may not be PPs.

The command byte includes a 1-bit packet ID. This toggles each time a new PP
is constructed. It is used by the recipient for duplicate detection. The
protocol forbids either node from sending a new payload until the prior one is
acknowledged. Consequently a single bit suffices as a packet ID.

## 9.2 Direction management

A difference between `Master` and `Slave` is that `Master` issues unsolicited
packets. `Slave` listens constantly and transmits exactly one packet each time
it receives a packet from `Master`. `Master` listens for a period after each
transmission: if nothing is received in that time it repeats the last packet
sent. After sending a packet in response to one received, `Slave` listens with an
infinite timeout. The concept here is that `Slave` will eventually receive a
packet from `Master`: if `Slave` timed out, there would be nothing it could do.
Sending is disallowed because `Master` might not be listening.

## 9.3 Packet management

`Master` controls the process by periodically sending packets. If it has data
to send they will carry a payload; otherwise they will be empty packets serving
to poll `Slave` which might have data to send. Likewise packets from `Slave`
may or may not carry a payload.

Any packet received by `Master` is an acknowledgement that the last packet it
sent was correctly received. If no packet is received in the timeout period
then either the transmitted packet or `Slave`'s response was lost. `Master`
continues transmitting the same packet until it receives a response.

In the case where `Slave` correctly received a PP, but its response was lost,
`Slave` will subsequently receive one or more duplicates: these are recognised
by virtue of the unchanged packet ID and discarded.

Responses from `Slave` may or may not be PPs (depending on whether the
application has queued a line for transmission). `Master` ignores non-PP
packets aside from recognising the implied acknowledgement of transmission. Any
payload is checked to see if it is a duplicate and, if not, appended to the
receive queue. Duplicates will occur if `Master`'s `ACK` is lost. `Master`
acknowledges all PPs so this sequence will end when connectivity is re-
established.

When `Slave` sends a PP it waits for an `ACK` packet from `Master` (if its PP
was lost, the received packet will be `MSG`). `Slave` continues to respond with
the same packet until `ACK` is received.

# 10. Performance

## 10.1 Message integrity

The script `as_nrf_test.py` transmits messages with incrementing ID's.
Reception checks for non-consecutive received ID's. Under normal conditions the
radio hardware ensures that received packets are correct, and the protocol
ensures that no packets are lost.

Testing was also done at the very limit of wireless range, outages occurring
about once per minute over 10 hours. After 612 outages one instance of data
corruption occurred. A packet had two bytes with single bit errors. It should
be noted that this was an extreme test. With better (but still imperfect)
connectivity no errors were observed in long periods of testing.

## 10.2 Latency and throughput

The interval between queueing a message for transmission and its complete
transmission depends on a number of factors, principally link quality and
message length. Each packet holds a maximum payload of 30 bytes; long messages
require successful transmission of each packet. Packet transmission takes a
minimum of 10ms but potentially much longer if retransmissions occur. In the
event of an outage latency can be as long as the outage duration.

Throughput will also depend on the number and nature of competing user tasks.
If a node sends a message, the peer checks for its arrival once per iteration
of the scheduler. The worst-case latency is the sum of the worst-case latency
imposed by each competing task.

# 11. Design notes

Both nodes delegate reception to the `iostream` mechanism. When an application
issues
```python
    res = await sreader.readline()
```
the `ioctl` method causes the coroutine to pause until data is available. In
the case of `Slave` data availability causes the `_process_packet` to update
the receive queue, trigger transmission of a response packet, and terminate.

In the case of `Master` a similar mechanism is used for incoming packets but
in this case an `Event` is triggered which is picked up by the continuously
running task `._run`.

The protocol works as follows. `Master` sends a packet, then waits on the
`Event`. This wait is subject to a timeout. If the `Event` is set, `Master` can
be sure that `Slave` received the packet: it updates the data to be transmitted
to the next packet (if any). If the timeout occurred, either `Slave` failed to
receive the packet or its response was lost. In either case, `Master`
retransmits the packet.

Retransmission implies that sometimes duplicate packets will be received. The
`Packet` class enables the recipient to detect and discard dupes by virtue of a
single bit packet ID.

`Slave` always responds to packet reception by immediately sending a single
response packet. Consequently any packet received by `Master` is an
acknowledgement of reception of `Master`'s last transmission.

This does not apply in the other direction. A response packet from `Slave`
containing data may be lost. In this case the next packet from `Master` would
result from the timeout. Consequently `Master` sends a specific `ACK` command
to acknowledge successful reception of a packet. `Slave` retransmits a packet
until it receives an `ACK`.

The protocol provides limited handling of power outages. If one node has an
outage while the other does not, the running node may receive an incomplete
`message`. The protocol detects this and discards the incomplete data. This
ensures that `message` instances should always have the expected structure,
but does imply message loss.

# 12. Notes for protocol designers

The nRF24l01 and its driver have the following "gotchas" calling for workrounds.
 1. The response from `.send_done` cannot be relied upon. A result code of 2
 indicates transmission failure. On occasion 2 is returned when successful
 reception has occurred.
 2. The `.send_done` response if the peer is down is to return `None` until
 connectivity resumes. This is reasonable but a protocol may need a timeout here.
 3. If a message is sent and you then wait for a response there is a risk that
 the reponder sends a reply before the sender's radio is receiving. This can be
 averted by ensuring that a minimum delay occurs between receiving a packet and
 transmitting a response.
 4. Under very rare conditions at the limit of range a corrupt packet may be
 received. I suspect this lay behind my failure to achieve 100% reliability
 with the old protocols. Here is the smoking gun.

Data sent:
```
b'[13398, 2, [62541, 0, 45113, 38714], "abcdefgh"]\n'
```
Data received:
```
JSON error b'\xdb13398, 2, [62541< 0, 45113, 38714], "abcdefgh"]\n'
```
Note `ord('[') == 0x5b`, `ord(',') == 0x2c`, and `ord('<') == 0x3c`. In each
case a 0 is received as a 1.

This occurred with the official driver on default settings apart from RF
channel.
