# micropython-radio

Three protocols for the nRF24L01+ radio module. All are based on a link between
two radios, where one acts as master (initiating communications) and the other
acts as slave (responding to transmissions). The async-radio-pickle hides this
underlying master/slave asymmetry.

radio-fast
----------

A protocol for short fixed-length records which trades the simplicity of use of
radio-pickle in exchange for higher speeds and (slightly) greater range.  
See [README](./radio-fast/README.md)

radio-pickle
------------

This offers a simple way to use the nRF24L01+ radio to exchange arbitrary
Python objects between two Pyboards. This is the easy way to do it!  
See [README](./radio-pickle/README.md)

async-radio-pickle
------------------

A version of radio-pickle which uses uasyncio to achieve non-blocking
behaviour. The unit of communication is an arbitrary Python object. It provides
a symmetrical Channel object enabling either end of the link to send
unsolicited messages. This enables the same code to run on both ends of the
link with the exception of a single boolean initialisation flag which must
differ at each end.

One aim of this was to achieve "reliable" communication in the sense that
messages would never be lost. If a unit moved out of range the message would
inevitably be delayed until it moved back into range - but it would eventually
get through. Alas this has not yet been achieved: under circumstances of poor
communication messages are occasionally lost.

See [README](./async-radio-pickle/README.md)

