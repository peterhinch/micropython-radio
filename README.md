# micropython-radio

This repo comprises two protocols for the nRF24L01+ radio module. Each
implements a bidirectional link between two radios.

## radio-fast

A driver for short fixed-length records. This is a thin layer over the official
driver which makes it easier to ensure mutually compatible configurations of
the radios. This is done by deploying a common config file to both nodes.

The nRF24L01 provides data integrity but successful reception is not guaranteed
as radio outages can occur (see below).

In this protocol one radio acts as master (initiating communications) and the
other acts as slave (responding to transmissions)

See [README](./radio-fast/README.md)

## as_nrf_stream.py

See [README](./async/README.md)

Radio links are inherently unreliable, not least since receiver and transmitter
may move out of range. The link may also be disrupted by radio frequency
interference. This driver mitigates this by ensuring that, in the event of a
link outage, data transfer resumes without loss when connectivity is restored.

The use of `uasyncio V3` stream I/O means that the interface matches that of
objects such as sockets and UARTs. Objects exchanged are `bytes` instances,
typically terminated by a newline character (`b'\n'`). Lengths of the `bytes`
objects are arbitrary and are allowed to vary at runtime. Consequently it is
easy to exchange Python objects via serialisation libraries such as `pickle`
and `ujson`.

The underlying protocol's API hides the following details:
 1. The radio hardware is half-duplex (it cannot simultaneously transmit and
 receive).
 2. The chip has a 32 byte limit on message length.
 3. To address point 1 the protocol is asymmetrical with a master/slave design
 which is transparent to the user.

The driver provides a symmetrical full-duplex interface in which either node
can initiate a transmission at any time. The cost relative to the `radio-fast`
module is some loss in maximum throughput and an increase in latency. Gains
are:
 * The ability to exchange relatively large, dynamic objects.
 * Data integrity with each message being correctly received exactly once.
 * A standard bidirectional (full duplex) stream interface.
 * Asynchronous code: in the event of an outage communication will inevitably
 stall for the duration, but other coroutines will continue to run.

## Obsolete modules

The `as_nrf_stream` driver replaces the old `radio-pickle` and
`async-radio-pickle` modules which pre-dated the `uasyncio` I/O interface. This
module is simpler, smaller and more efficient. Lastly the old asynchronous
driver allowed duplicate messages to be received. The new protocol ensures that
each record is received exactly once.
