# micropython-radio

Two protocols for the nRF24L01+ radio module. Both are based on a link between
two radios, where one acts as master (initiating communications) and the other
acts as slave (responding to transmissions).

radio-pickle
------------

This offers a simple way to use the nRF24L01+ radio to exchange arbitrary
Python objects between two Pyboards. This is the easy way to do it!  
See [README](./radio-pickle/README.md)

async-radio-pickle (in development: do not use!)
------------------

A version of radio-pickle which uses uasyncio to achieve non-blocking
behaviour.  
See [README](./async-radio-pickle/README.md)

radio-fast
----------

A protocol for short fixed-length records which trades the simplicity of use of radio-pickle in exchange for
higher speeds and (slightly) greater range.  
See [README](./radio-fast/README.md)

