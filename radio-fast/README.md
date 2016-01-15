The radio_fast module
---------------------

This module uses the nRF24l01+ chip and MicroPython driver to create a wireless link between two points.
Wherease the radio_pickle module is designed for ease of use and support of dynamically variable data,
radio_fast is optimised for speed and range. The cost is a restriction to a fixed record length determined
at the design time of your application. Further, a grasp of the Python ``struct`` module is required to
customise the message format for the application. The file ``config.py`` is intended for adaptation by
the user to define message formats and hardware onfiguration.

The payoff is a typical turnround time of 4mS for exchanging 12 byte messages. This can potentially be
improved - at some cost in range - by using one of the nRF24l01's high speed modes.

Introduction
------------

The first bit of advice to anyone considering using this chip is to buy a decent quality breakout board.
Many cheap ones work poorly, if at all. I've used Sparkfun boards to good effect.

The nRF24l01+ is a highly versatile device, but for many applications only a subset of its capabilities
is required. In particular significant simplifications are possible if you need to communicate between
two devices only, and can adopt "half duplex" communications. A half duplex link is one where one device acts
as a master and the other a slave. Only the master is permitted to send unsolicited messages: if it wants
a response from the slave it sends a request and awaits the response. The slave must always respond. This
restriction ensures that you don't encounter the case where both ends transmit at the same time, simplifying
the programming. Many applications fit this model naturally, notably remote control/monitoring and data logging.

The nRF24l01 aims to provide "reliable" communication in a manner largely hidden from the user. Here the
term "reliable" means that messages will always have the correct contents. It does not mean that a message
will always get through: the nature of wireless communication precludes this. The transmitter may have
moved out of range of the receiver or interference may make communication impossible - "The falcon
cannot hear the falconer...". A communications protocol is required to ensure that the master and slave
are correctly synchronised in the presence of errors and regain synchronisation after a timeout. It must
also provide feedback to the user program as to whether communications were successful. This driver
implements such a protocol.

"Reliable" communications are achieved by the nRF24l01 as follows. When one device transmits a message it
includes a CRC code. The receiver checks this, if it matches the data it's received it sends back an
acknowledgement, otherwise it sends back an error code. In the latter case the transmission and checking
process is repeated. This continues until either the data is received successfully or a defined number of
attempts is reached. All this happens entirely without programmer intervention. However it does mean that
sending a message takes a variable length of time depending on factors such as distance and interference.

Dependencies
------------

The library requires the nrf24l01.py driver from the source tree.
[nrf24l01.py](https://github.com/micropython/micropython/tree/master/drivers/nrf24l01)

Example code
------------

The following samples show typical usage. To run these you need to edit ``config.py`` which
defines hardware connections and message formats.

```python
import pyb
import radio_fast as rf
from config import master_config, slave_config  # Configs for the hardware

messages = rf.MessagePair()                     # Instantiate messages and check compatibility
def test_slave():
    s = rf.Slave(slave_config, messages)
    while True:
        result = s.exchange(block = True)       # Wait for master
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        messages.to_master.i0 += 1

```

```python
import pyb
import radio_fast as rf
from config import master_config, slave_config  # Configs for the hardware

messages = rf.MessagePair()                     # Instantiate messages and check compatibility
def test_master():
    m = rf.Master(master_config, messages)
    while True:
        result = m.exchange()
        if result is not None:
            print(result.i0)
        else:
            print('Timeout')
        messages.from_master.i0 += 1
        pyb.delay(1000)
```

Module radio_fast.py
--------------------

Class Master
~~~~~~~~~~~~

This is subclassed from RadioFast which is subclassed from NRF24L01 in nrf24l01.py.

Constructor

This takes two mandatory arguments, a ``RadioConfig`` object and a ``MessagePair`` object. The former
(defined in ``config.py``) details the connections to the nRF24l01 module and channel in use. The latter
contains the messages to be exchanged between the devices, again defined in ``config.py``.

method exchange()

No arguments. Attempts to send a message to the slave and accept a response.

Results.

On success, returns a ``ToMaster`` message object.
On timeout returns None.

Class Slave
~~~~~~~~~~~

This is subclassed from RadioFast which is subclassed from NRF24L01 in nrf24l01.py.

Constructor

This takes two mandatory arguments, a ``RadioConfig`` object and a ``MessagePair`` object. The former
(defined in ``config.py``) details the connections to the nRF24l01 module and channel in use. The latter
contains the messages to be exchanged between the devices, again defined in ``config.py``.

method exchange()

Argument ``block`` Boolean, default False. Determines whether ``exchange()`` waits for a transmission
from the master (blocking transfer) or returns immediately with a status. If a message is received from the
master it is unpacked. The return message is packed and transmitted to the master.

Results.

On success, returns a ``FromMaster`` message object.
On timeout returns None.
If no data has been sent (nonblocking read only) returns False.

Class RadioFast
~~~~~~~~~~~~~~~

This is subclassed from NRF24L01 in nrf24l01.py. It contains one user configurable class variable ``timeout``
which determines the maximum time ``Master`` or ``Slave`` instances will wait to send or receive a message.
In practice with short messages the radio times out in less than the default of 100mS, but this variable aims
to set an approximate maximum.

Class MessagePair
~~~~~~~~~~~~~~~~~

Master and slave modules must instantiate this class. It contains a ``FromMaster`` and a ``ToMaster``
message (defined in config.py) and is required to instantiate ``Master`` and ``Slave`` objects. Its
constructor takes no arguments.

Instance variables

from_master ``FromMaster`` message object
to_master ``ToMaster`` message object

Module config.py
----------------

This module defines the message format for messages from master to slave and from slave to master. As
configured three integers are sent in either direction - in practice these message formats will need to
be adjusted to suit the application. Both messages must pack to the same length: if neccessary use
redundant data items to achieve this. An assertion failure will be raised if this condition is not met.

It also implements the ``RadioConfig`` class that defines the hardware connections to the nRF24l01 and
the channel in use.

Classes FromMaster and ToMaster
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These define the message contents for messages sent from master to slave and vice versa. To adapt these
for an application the instance variables, ``fmt`` format string, ``pack()`` and ``unpack()`` methods
will need to be adjusted. Message formats may differ so long as their packed sizes are identical and in
range 1 to 32 bytes.

Class RadioConfig
~~~~~~~~~~~~~~~~~

This should be fairly self-explanatory: it provides a means of defining physical connections to the
nRF24l01 and the channel number (the latter must be identical for both ends of the link).

Performance
-----------

With messages of 12 bytes under good propagation conditions a message exchange takes about 4mS. Where
timeouts occur these take about 25mS

Channels
--------

The RF frequency is determined by the ``RadioSetup`` instance as described above. The ``channel`` value maps
onto frequency by means of the following formula:
freq = 2400 + channel [MHz]
The maximum channel no. is 125. The ISM (Industrial, Scientific and Medical) band covers 2400-2500MHz and is
licensed for use in most jurisdictions. It is, however, shared with many other devices including WiFi, Bluetooth
and microwave ovens. WiFi and Bluetooth generally cut off at 2.4835GHz so channels 85-99 should avoid the risk
mutual interefrence. Note that frquencies of 2.5GHz and above are not generally licensed for use: check local
regulations before using these devices.

FILES
-----

radio_fast.py The driver.  
config.py Example config module. Adapt for your wiring and message formats.  
tests.py Test programs to run on any Pyboard/nRF24l01.  
rftest.py, nbtest.py Test programs for my own specific hardware. These illustrate use with an LCD display and microthreading
scheduler. The latter tests slave nonblocking reads.  
README.md This file
