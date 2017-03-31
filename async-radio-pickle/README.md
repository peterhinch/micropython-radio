# async_radio_pickle

TODO: write it!

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
