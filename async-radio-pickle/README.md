# async_radio_pickle

The test scripts have now been updated for `uasyncio` V3 and require this
version. To ensure this, use a daily build of firmware or a release build after
V1.2.

This provides a means of creating a point-to-point radio link capable of
exchanging arbitrary Python objects. It uses ``uasyncio`` for nonblocking
behaviour. Communication is by ``Channel`` instances which provide a
common API for both ends of the link.

[Back](../README.md)

# Dependencies

The library requires the pickle module from micropython-lib and the nrf24l01.py
driver from the source tree.  
[nrf24l01.py](https://github.com/micropython/micropython/tree/master/drivers/nrf24l01)  
[pickle.py](https://github.com/micropython/micropython-lib/tree/master/pickle)

It requires the uasyncio library. One way to install it is to build the Unix
version. Then use upip to install it as per the instructions
[here](https://github.com/micropython/micropython-lib). Then recursively copy
the contents of ``~/.micropython/lib`` to the target hardware.

# Test Programs

These assume a pair of Pyboards with nrf24l01+ radios. The config file
``myconfig.py`` should be edited to reflect your SPI bus number and pins used
for the radio's csn and ce pins.

 * ``simple_test.py`` Basic test.
 * ``as_rp_test.py`` Shows statistics on duplicated and missing messages along
 with RAM usage.

# The Channel class

This is the means of accessing the radio link. The link is half-duplex,
consequently there is an inherent asymmetry inasmuch as only one end (termed
the master) can transmit spontaneously. The slave only transmits in response to
receiving from the master. The ``Channel`` class hides this asymmetry and
provides a similar interface to each end of the link enabling both ends to send
unsolicited messages.

It should be noted that this flexibility and ease of use comes at a price in
performance. Where speed is critical the ``radio_fast`` library should be used.

## Constructor

Mandatory positional arguments:
 * ``config`` A RadioSetup instance defining the hardware config and radio
 channel.
 * ``master`` A boolean. The protocol is effectively symmetrical but one end
 must be set ``True`` and the other end ``False``.

Optional keyword arguments. These enable callbacks to be provided. Callbacks
should be designed to execute as quickly as possible.
 * ``txcb`` This callback will be called when the transmitter is ready.
 * ``rxcb`` Will be called when data has been received. It takes a single arg
 being the received object.
 * ``statecb`` This will be called when the link state changes (i.e. a timeout
 has occurred). It takes a single boolean argument, ``True`` if the new link
 state is OK.
 * ``txqsize`` Size of transmit queue. Default 20 Python objects.

Note that for bidirectional communication a receive callback is necessary. A
transmit callback is only required if data must be queued for transmission as
soon as possible. Otherwise use the methods below to send data as it becomes
available.

## Methods

These are synchronous and return immediately.

 * ``txready`` No args. Returns ``True`` if the transmitter queue can accept
 data, ``False`` if it is full with objects pending transmission.
 * ``send`` Takes one arg, the object to send. If the transmit queue is full it
 returns ``False`` signifying failure. Returns ``True`` on success.

## Property

 * ``link`` A boolean providing the current 'link up' status.

## Usage

A ``Channel`` instance has a transmitter queue: the ``send`` method stores an
object for transmission and will attempt to send it when possible. Consequently
the ``txready`` status should be checked before sending. Alternatively the
return value from the ``send`` method should be checked to ensure that the
object was successfully queued for transmission.

Transmission of the ``None`` object will have no effect. However ``None`` may
be a part of another Python object such as ``[None]``.

Data reception triggers a user supplied callback which should process the data
as required by the application. On completion of the callback the ``Channel``
prepares the receiver for the next object.

## Mode of operation 

A ``Channel`` instance behaves as follows. If it has data to send there may be
some latency before transmission occurs. This latency depends on the link
status and on whether the channel was instantiated with ``master`` set.

If ``master`` was ``False`` transmission will not occur until a block is
received from the master.

If the channel is OK (i.e. the last exchange was successful) the master will
pause for 100ms before sending a block. It will do this even if it has no data
to send, to ensure that the slave can send data if it has an item in its queue.
So, with reliable radio communications, latency is on the order of 100ms.

If the last exchange failed the master will wait for a period to allow the
slave to time out and will attempt to repeat the failed transfer. This can
result in arbitrarily long periods of latency depending on the link conditions:
if the units have moved out of radio range the delay will persist until this is
corrected.

This will not cause the application code to block: the consequence is that the
receive callback will be delayed and the transmit queue may become full. The
application design should accommodate this possibility.

# RadioSetup class

This is intended to facilitate sharing a configuration between devices to
reduce the risk of misconfiguration. A RadioSetup object may be instantiated
and configured in a module common to both ``Channel`` instances e.g. 
``myconfig.py``.

## Class variable

``channel`` Defines the radio's carrier frequency. This must be identical for
both ``Channel`` instances. See notes below.

## Constructor

This takes the following keyword only arguments:  
 * ``spi_no`` SPI bus no.  
 * ``csn_pin`` Pyboard pin used for CSN expressed as a string.  
 * ``ce_pin`` Pyboard pin used for CE expressed as a string.

``Channel`` instances may differ in respect of these values depending on your
hardware.  

# Protocol characteristics

While a message comprises a Python object of arbitrary size, the protocol works
best with small objects. This is because the nrf24l01 has a maximum payload
size of 32 bytes. To send a large object implies the successful transmission of
a number of consecutive blocks. If this fails (and radio links can always fail)
the entire set is retransmitted. On a poor quality link the time to success
will increase with message size.

The design aims to ensure messages are never missed. This has the consequence
that if the radio link goes down for a period, the message will remain queued
for the duration. This may be arbitrarily long - for example if the units move
out of range of each other.

If the sender fails to receive a BYE acknowledgement of reception it deems the
transmission to have failed and re-transmits the object. Occasionally the
receiver sends BYE but the sender fails receive it. In this instance the sender
retransmits and the receiver gets a duplicate message. If this is an issue it
should be handled at the application level. One way is to send an incrementing
modulo N message ID as part of the object, with the receiver discarding objects
already received.

The protocol is described in detail [here](../PROTOCOL.md)

# The Pickle protocol

The driver is subject to the same limitations as the Python pickle module it
uses. All Python built-in data types (lists, strings, dictionaries and
suchlike) are supported. There are constraints regarding custom classes - see
the Python documentation. MicroPython has restrictions on subclassing built in
types.

Currently there is a MicroPython issue #2280 where a memory leak occurs if an
object tontains a string which varies regularly. The MicroPython interpreter
(which is invoked by Pickle) interns a copy of the string (if it hasn't already
occurred) each time until RAM is exhausted. The workround is to use data types
other than strings or bytes objects.

# Channels

The RF frequency is determined by the ``RadioSetup`` instance as described
above. The ``channel`` value maps onto frequency by means of the following
formula:  
freq = 2400 + channel [MHz]  
The maximum channel no. is 125. The ISM (Industrial, Scientific and Medical)
band covers 2400-2500MHz and is licensed for use in most jurisdictions. It is,
however, shared with many other devices including WiFi, Bluetooth and microwave
ovens. WiFi and Bluetooth generally cut off at 2.4835GHz so channels 85-99
should avoid the risk of mutual interefrence. Note that frequencies of 2.5GHz
and above are not generally licensed for use: check local regulations before
using these frequencies.
