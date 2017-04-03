# async_radio_pickle

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

# The Channel class

This is the means of accessing the radio link. The link is half-duplex,
consequently there is an inherent asymmetry in that only one end (the master)
can transmit spontaneously. The slave only transmits in response to receiving
from the master. The ``Channel`` class aims to hide this asymmetry providing a
similar interface to each end of the link.

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

Note that for bidirectional communication a receive callback is necessary. A
transmit callback is only required if data must be transmitted as soon as
possible. Otherwise use the methods below to send data as it becomes available.

## Methods

These are synchronous and return immediately.

 * ``txready`` No args. Returns ``True`` if the transmitter can accept data,
 ``False`` if a data item is pending transmission.
 * ``send`` Takes one arg, the data to send. Does nothing, returning ``False``,
 if the transmitter is not ready.
 * ``up`` No args. Returns a boolean providing the current 'link up' status.

## Class variable

There is a single class variable ``latency_ms`` defaulting to 1000. See below
for the significance of this.

## Usage

A ``Channel`` instance does not maintain transmitter or receiver queues: it
stores a single item of data for transmission and a single item of received
data. Queues may be maintained by the application if required. Consequently
the ``txready`` status should be checked before sending. Alternatively the
return value from the ``send`` method should be checked to ensure that the
data item was successfully scheduled for transmission.

Data reception triggers a user supplied callback which should process the data
as required by the application. On completion of the callback the ``Channel``
prepares the receiver for the next data item.

## Mode of operation 

A ``Channel`` instance behaves as follows. If it has data to send it attempts
to send it immediately. How soon it is actually transmitted depends on whether
the channel was instantiated with ``master`` set. If so, it is transmitted
immediately. Otherwise it will wait until the master next transmits.

In the event that the master has no data to send it ensures that it can receive
data from the slave in a reasonably timely fashion by sending no data once the
latency timer has expired. Setting the latency timer to short values may not
achieve expected results: in the event of communications problems
retransmissions take place. There is an underlying timeout of 300ms where the
link is defined as having failed. So there are practical lower limits to the
latency, though low values should not cause failure of the driver.

If the application requires minimum transmission latency in one direction, the
``Channel`` doing the transmission should be instantiated as master.

# RadioSetup class

This is intended to facilitate sharing a configuration between devices to
reduce the risk of misconfiguration. A RadioSetup object may be instantiated
and configured in a module common to both ``Channel`` instances.

## Class variable

``channel`` Defines the radios' carrier frequency. This must be identical for
both ``Channel`` instances. See notes below.

## Constructor

This takes the following keyword only arguments:  
 * ``spi_no`` SPI bus no.  
 * ``csn_pin`` Pyboard pin used for CSN expressed as a string.  
 * ``ce_pin`` Pyboard pin used for CE expressed as a string.

``Channel`` instances may differ in respect of these values depending on your
hardware.  

# The Pickle protocol

The driver is subject to the same limitations as the Python pickle module it
uses. All Python built-in data types (lists, strings, dictionaries and
suchlike) are supported. There are constraints regarding custom classes - see
the Python documentation. MicroPython has restrictions on subclassing built in
types.

Currently there is a MicroPython issue #2280 where a memory leak occurs if you
pass a string which varies regularly. Pickle saves a copy of the string (if it
hasn't already occurred) each time until RAM is exhausted. The workround is to
use any data type other than strings or bytes objects.

The protocol is described in detail [here](../PROTOCOL.md)

# Channels

The RF frequency is determined by the ``RadioSetup`` instance as described
above. The ``channel`` value maps onto frequency by means of the following
formula:  
freq = 2400 + channel [MHz]  
The maximum channel no. is 125. The ISM (Industrial, Scientific and Medical)
band covers 2400-2500MHz and is licensed for use in most jurisdictions. It is,
however, shared with many other devices including WiFi, Bluetooth and microwave
ovens. WiFi and Bluetooth generally cut off at 2.4835GHz so channels 85-99
should avoid the risk mutual interefrence. Note that frequencies of 2.5GHz and
above are not generally licensed for use: check local regulations before using
these frequencies.
