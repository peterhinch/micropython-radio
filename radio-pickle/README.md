The radio_pickle module
-----------------------

This module uses the nRF24l01+ chip and MicroPython driver to create a wireless link between two points.
The aim is to simplify the use of these radios to the point where they can be used by anyone with a basic
knowledge of Python. This simplicity is achieved at some cost in performance. The driver enables arbitrary
Python objects to be exchanged between the two devices. The size of these objects may change dynamically
as the user program runs. Python's pickle module is employed for object serialisation.

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
sending a message takes a variable length of time depending on factors such as distance and intereference.

Dependencies
------------

The library requires the pickle module from micropython-lib and the nrf24l01.py driver from the source
tree.  
[nrf24l01.py](https://github.com/micropython/micropython/tree/master/drivers/nrf24l01)  
[pickle.py](https://github.com/micropython/micropython-lib/tree/master/pickle)

Example code
------------

```python
def test_slave():
    import radio_pickle as rp
    s = rp.Slave(rp.RadioSetup(spi_no = 1, csn_pin = 'X5', ce_pin = 'X4'))
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
            obj[0] += 1 # modify the object transmitted: demo variable object size
            obj[1] = obj[1] + chr(x) if len(obj[1]) < 60 else '' # Keep from getting too huge
            x = x +1 if x < ord('z') else ord('a') 
```

```python
def test_master():
    import radio_pickle as rp
    m = rp.Master(rp.RadioSetup(spi_no = 1, csn_pin = 'X5', ce_pin = 'X4'))
    obj = [0, ''] # object to be sent
    while True:
        try:
            result = m.exchange(obj)
        except OSError: # Optionally trap timeout errors (e.g. out of range)
            print("Timeout")
        else:
            print(result) # No errors raised
        pyb.delay(1000) # send 1 message per sec
        obj[0] += 1 # modify data
```

Class RadioSetup
----------------

This is intended to facilitate sharing a configuration between master and slave devices to reduce the
risk of misconfiguration. A RadioSetup object may be instantiated and configured in a module common
to master and slave.

Class variables
~~~~~~~~~~~~~~~

These must be identical for master and slave.  
``payload_size`` The driver requires a value of 32.  
``channel`` Defines the radios' carrier frequency. See notes below.  

Constructor
~~~~~~~~~~~

This takes the following keyword only arguments:  
``spi_no`` SPI bus no.  
``csn_pin`` Pyboard pin used for CSN expressed as a string.  
``ce_pin`` Pyboard pin used for CE expressed as a string.  
Master and slave may differ depending on your hardware  

Class Master
------------

This is subclassed from TwoWayRadio which is subclassed from NRF24L01 in nrf24l01.py.

Methods
~~~~~~~

Constructor
~~~~~~~~~~~

This takes a single argument, a RadioSetup instance.

exchange
~~~~~~~~

This takes a single argument, an arbitrary Python object, defaulting to ``None``. If the exchange
compeletes successfully it returns the object provided by the slave. A protocol failure caused by
poor commmunications will result in an ``OSError``. The caller should trap these with ``pass`` or
appropriate code depending on the program logic.

Class Slave
-----------

This is subclassed from TwoWayRadio which is subclassed from NRF24L01 in nrf24l01.py.

Constructor
~~~~~~~~~~~

This takes a single argument, a RadioSetup instance.

exchange
~~~~~~~~

From the point of view of the slave an exchange can only begin when the master initiates
an exchange.

The method takes a single argument, an arbitrary Python object, defaulting to ``None``. It is a
nonblocking method returning immediately if no data has been sent. If the exchange compeletes
successfully it returns the object snet by the master. If the master has not initiated an exchange
it will raise a ``NoData`` exception. The user should periodically poll ``exchange()``, ignoring
``NoData`` and processing received data only where no exception occurs (see example above). A protocol
failure caused by poor commmunications will result in an ``OSError``.  The caller should trap these
with ``pass`` or appropriate code depending on the program logic.

Note that if the master moves out of range the slave will only see a timeout if a transfer failed.
If it moves out of range between transfers the slave will (inevitably) simply fail to receive further
messages. This can be detected by implementing a timeout.

Exceptions
----------

``NoData`` Raised by slave only. Indicates master has sent no data.  
``OSError`` On initialisation it means hardware cannot be detected. At runtime it indicates a protocol
failure, normally a timeout.

Performance
-----------

This driver trades performance for simplicity and flexibility of use. An exchange of small objects takes about
17mS under good propagation conditions. Larger objects increase the time linearly at about 17mS for every
additional 30 bytes over the first 30. Poor conditions increase the time further. The transfer speed of the
nRF24l01 may be improved: the driver uses 250K bits/sec which optimises range. Higher speeds may be employed.
See ``set_power_speed()`` in the NRF24L01 library. Master and slave must use the same values.

As the devices are moved further apart the time to exchange small objects gradually increases to typically
50mS as the chip and the driver struggle to communicate. The driver also requests retransmission
if a response to an individual transmission is not received within a fixed period.

If a timeout occurs an ``OSError` will be raised in about 120mS although this can be longer if repeated
retries occur before the failure. The absolute maximum depends on conditions and message length but it
can be calculated and is finite :)

For best performance a protocol based on fixed size, byte packed records should be used. The ``ustruct`` module
facilitates packing data into bytes far more efficiently than pickle. This is at a cost in programming complexity and
flexibility as, unlike this driver, record structure and length are set in code. I intend to write such a driver.

The TwoWayRadio Class - tweaking performance
--------------------------------------------

This supports functionality common to slave and master. It has the following class variables which may be
altered to fine-tune performance at the limits of range or under poor propagation conditions.

``timeout`` The time in mS that transmitter and receiver wait for the other to respond.  
``max_resend_requests`` Maximum number of times a resend request will be sent.  
``bye_no`` Number of times the BYE command is sent.

There is a general point here as to the degree to which the protocol should attempt to recover from errors.
Doing so increases the maximum time it spends handling an exchange which may ultimately fail. An alternative
approach is to set ``max_resend_requests`` to zero, ``bye_no`` to one and let the application code attempt
the exchange again. I suspect that the benefits of letting the protocol handle it increase with the message
length; a notion I haven't tested.

The Pickle protocol
-------------------

The driver is subject to the same limitations as the Python pickle module it uses. All Python built-in data
types (lists, strings, dictionaries and suchlike) are supported. There are constraints regarding custom
classes - see the Python documentation. MicroPython has restrictions on subclassing built in types.

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

radio_pickle.py The driver.  
myconfig.py Example config module used by test.py. Adapt for your wiring.  
test.py Test programs to run on any Pyboard/nRF24l01.  
rptb.py Test programs for my own specific hardware. test() illustrates use with an LCD display and microthreading
scheduler  
protocol.md Description of the commmunications protocol.  
README.md This file
