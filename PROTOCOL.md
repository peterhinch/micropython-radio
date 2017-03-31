# RADIO_PICKLE PROTOCOL

[Back](./README.md)

## MESSAGE FORMAT


Messages consist of a 32 byte bytearray
b[0] is a command byte
b[1] is the bytecount of the data (0..30)

## COMMANDS

Commands are ``OK``, ``RESEND``, ``BYE` and ``START_SLAVE``.  
``OK`` and ``START_SLAVE`` carry data while ``RESEND`` and ``BYE`` have a bytecount of zero
Commands carrying data have the ``TXDONE`` bit of the command byte set if reception of the
message completes the data transfer.

## PROTOCOL

The slave checks for a ``START_SLAVE`` message from the master. If none is present
it raises a ``NoData`` exception: the calling program should repeatedly call
the ``exchange()`` method ignoring ``NoData`` exceptions.

When a ``START_SLAVE`` is received the slave processes the data. From then on a
symmetrical protocol ensues, with the slave sending an ``OK`` message to the master. From this
point the protocol is described in terms of transmitter and receiver, with slave and
master exchanging roles until termination. Initially the master starts is the transmitter,
but once the slave receives ``START_SLAVE`` it adopts the role before handing it back to the master.

The transmitter behaves as follows, depending on the received command:  
If it has received an ``OK`` or ``RESEND`` message, it responds as follows:  
 If it has data to send, it sends an ``OK`` message with as much outstanding data as will
 fit in the bytearray. If this completes the data to be sent, the ``TXDONE`` bit will be set.  
 If the message was ``RESEND`` the data is that which was last sent, otherwise the next
 packet is sent.  
 If it has no data to send, it checks whether the received message had ``TXDONE`` set.  
  If it had, it terminates the transfer with ``BYE`` (see below) and makes a normal exit.  
  If ``TXDONE`` was not sent, it sends a zero length ``OK`` message prompting the receiver
  to send another message.  
If the transmitter receives ``BYE`` it makes a normal exit (it does not reply).  
If it receives ``START_SLAVE`` (which should never occur) it raises ``OSError``.  
If the message was not received within a timeout, it sends a ``RESEND`` message with
no data. This is repeated upto ``TwoWayRadio.max_resend_requests`` times.  
If the message is still not received it proceeds as follows.  
 If it has read all the expected data makes a normal exit.  
 Otherwise it raises an `OSError`` to signify a failed transfer.

### Termination

The protocol is terminated by the current transmitter sending ``TwoWayRadio.bye_no`` ``BYE``
messages in quick succession (20mS timeout). No reply is expected.

### Message send

This is subject to a timeout. The transmitter will attept an ``NRF24L01.send()`` with the
timeout value specified. If it returns before the timeout has expired this will be repeated
until the timeout expires, when an ``OSError`` will be returned to the caller. The
timeout is defined in ``TwoWayRadio.timeout`` and is currently 100mS. The aim is that
approximately the same timeout value applies to the transmitter and the receiver
(``TxMessage.sendbuf() and ``TwoWayRadio.await_message()`` respectively).

## USAGE

Typical master code, assuming a master has been instantiated as ``m``, is as follows:

```python
    while True:
        try:
            result = m.exchange(obj)
        except OSError: # Optionally trap timeout errors (e.g. out of range)
            print("Timeout") # otherwise pass
        else:
            # result has been received: process the data
        pyb.delay(1000) # choose a repetition rate
```

Typical slave code, assuming the slave has been instantiated as ``s``, is as follows:


```python
    while True:
        try:
            result = s.exchange(obj)
        except rp.NoData:              # Master has sent nothing
            pass
        except OSError:                 # Optionally trap, otherwise pass
            print("Timeout")
        else:
            # result has been received: process the data
```