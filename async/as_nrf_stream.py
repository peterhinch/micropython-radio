# as_nrf_stream.py uasyncio stream interface for nRF24l01 radio

# (C) Peter Hinch 2020
# Released under the MIT licence

import io
import ustruct
import uasyncio as asyncio
from time import ticks_ms, ticks_diff
from micropython import const
from nrf24l01 import NRF24L01

__version__ = (0, 1, 0)

# I/O interface
MP_STREAM_POLL_RD = const(1)
MP_STREAM_POLL_WR = const(4)
MP_STREAM_POLL = const(3)
MP_STREAM_ERROR = const(-1)

# Command bits. Notionally LS 4 bits are command, upper 4 status
MSG = const(0)  # Normal packet. May carry data.
ACK = const(1)  # Acknowledge. May carry data.
PWR = const(0x40)  # Node has powered up: peer clears rxq.
PID = const(0x80)  # 1-bit PID.
CMDMASK = const(0x0f)  # LS bits is cmd

# Timing
SEND_DELAY = const(10)  # Transmit delay (give remote time to turn round)

# Optional statistics
S_RX_TIMEOUTS = 0
S_TX_TIMEOUTS = 1
S_RX_ALL = 2
S_RX_DATA = 3

# Packet class creates nRF24l01 a fixed size 32-byte packet from the tx queue
class Packet:
    def __init__(self):
        self._fmt = 'BB30s'  # Format is cmd nbytes data

class TxPacket(Packet):
    def __init__(self):
        super().__init__()
        self._buf = bytearray(32)
        self._pid = 0
        self._len = 0
        self._ploads = 0  # No. of payloads sent

    # Update command byte prior to transmit. Send PWR bit until 2nd update: by
    # then we must have had an ACK from 1st payload.
    def __call__(self, txcmd):
        self._buf[0] = txcmd | self._pid if self else txcmd
        # 1st packet has PWR bit set so RX clears down rxq. 
        if self._ploads < 2:  # Stop with 2nd payload.
            self._buf[0] |= PWR
        return self._buf

    # Update the buffer with data from the tx queue. Return the new reduced
    # queue instance.
    def update(self, txq):
        txd = txq[:30]  # Get current data for tx up to interface maximum
        self._len = len(txd)
        if self:  # Has payload
            self._pid ^= PID
        ustruct.pack_into(self._fmt, self._buf, 0, 0, self._len, txd)
        if self._ploads < 2:
            self._ploads += 1  # Payloads sent.
        return txq[30:]

    def __bool__(self):  # True if packet has payload
        return self._len > 0

class RxPacket(Packet):
    def __init__(self):
        super().__init__()
        self._pid = None  # PID from last data packet

    def __call__(self, data):  # Split a raw 32 byte packet into fields
        rxcmd, nbytes, d = ustruct.unpack(self._fmt, data)
        cmd = rxcmd & CMDMASK  # Split rxcmd byte
        rxpid = rxcmd & PID
        pwr = bool(rxcmd & PWR)  # Peer has power cycled.
        dupe = False  # Assume success
        if nbytes:  # Dupe detection only relevant to a data payload
            if (self._pid is None) or (rxpid != self._pid):
                # 1st packet or new PID received. Not a dupe.
                self._pid = rxpid  # Save PID to check next packet
            else:
                dupe = True
        return d[:nbytes], cmd, dupe, pwr

# Base class for Master and Slave
class AS_NRF24L01(io.IOBase):
    pipes = (b'\xf0\xf0\xf0\xf7\xe1', b'\xf0\xf0\xf0\xf7\xd2')

    def __init__(self, config):
        master = int(isinstance(self, Master))
        # Support gathering statistics. Delay until protocol running.
        self._is_running = False
        if config.stats:
            self._stats = [0, 0, 0, 0]
            self._do_stats = self._stat_update
        else:
            self._stats = None
            self._do_stats = lambda _ : None

        self._tx_ms = config.tx_ms  # Max time master or slave can transmit
        radio = NRF24L01(config.spi, config.csn, config.ce, config.channel, 32)
        radio.open_tx_pipe(self.pipes[master ^ 1])
        radio.open_rx_pipe(1, self.pipes[master])
        self._radio = radio
        self._txq = b''  # Transmit and receive queues
        self._rxq = b''
        self._txpkt = TxPacket()
        self._rxpkt = RxPacket()
        self._tlast = ticks_ms()  # Time of last communication
        self._txbusy = False  # Don't call ._radio.any() while sending.

    # **** uasyncio stream interface ****
    def ioctl(self, req, arg):
        ret = MP_STREAM_ERROR
        if req == MP_STREAM_POLL:
            ret = 0
            if arg & MP_STREAM_POLL_RD:
                if not self._txbusy and (self._radio.any() or self._rxq):
                    ret |= MP_STREAM_POLL_RD
            if arg & MP_STREAM_POLL_WR:
                if not self._txq:
                    ret |= MP_STREAM_POLL_WR
        return ret

    # .write is called by drain - ioctl postpones until .txq is empty
    def write(self, buf):
        self._txq = bytes(buf)  # Arg is a memoryview
        return len(buf)  # Assume eventual success.

    # Return a maximum of one line; ioctl postpones until .rxq is not
    def readline(self):  # empty or if radio has a packet to read
        if self._radio.any():
            self._process_packet()  # Update ._rxq
        n = self._rxq.find(b'\n') + 1
        if not n:  # Leave incomplete line on queue.
            return b''
        res = self._rxq[:n]  # Return 1st line on queue
        self._rxq = self._rxq[n:]
        return res

    def read(self, n):
        if self._radio.any():
            self._process_packet()
        res = self._rxq[:n]
        self._rxq = self._rxq[n:]
        return res

    # **** private methods ****
    # Control radio tx/rx
    def _listen(self, val):
        if val:
            self._radio.start_listening()  # Turn off tx
            self._txbusy = False
        else:
            self._txbusy = True  # Prevent calls to ._process_packet
            self._radio.stop_listening()

    # Send a 32 byte buffer subject to a timeout. The value returned by
    # .send_done does not reliably distinguish success from failure.
    # Consequently ._send makes no attempt to distinguish success, fail and
    # timeout. This is handled by the protocol.
    async def _send(self, buf):
        self._listen(False)
        await asyncio.sleep_ms(SEND_DELAY)  # Give remote time to start listening
        t = ticks_ms()
        self._radio.send_start(buf)  # Initiate tx
        while self._radio.send_done() is None:  # tx in progress
            if ticks_diff(ticks_ms(), t) > self._tx_ms:
                self._do_stats(S_TX_TIMEOUTS)  # Optionally count instances
                break
            await asyncio.sleep_ms(0)  # Await completion, timeout or failure
        self._listen(True)  # Turn off tx

    # Update an individual statistic
    def _stat_update(self, idx):
        if self._stats is not None and self._is_running:
            self._stats[idx] += 1

    # **** API ****
    def t_last_ms(self):  # Return the time (in ms) since last communication
        return ticks_diff(ticks_ms(), self._tlast)

    def stats(self):
        return self._stats

# Master sends one ACK. If slave doesn't receive the ACK it retransmits same data.
# Master discards it as a dupe and sends another ACK.
class Master(AS_NRF24L01):
    def __init__(self, config):
        from uasyncio import Event
        super().__init__(config)
        self._txcmd = MSG
        self._pkt_rec = Event()
        asyncio.create_task(self._run())

    async def _run(self):
        # Await incoming for 1.5x max slave transmit time
        rx_time = int(SEND_DELAY + 1.5 * self._tx_ms) / 1000  # Seem to have lost wait_for_ms
        while True:
            self._pkt_rec.clear()
            await self._send(self._txpkt(self._txcmd))
            # Default command for next packet may be changed by ._process_packet
            self._txcmd = MSG
            try:
                await asyncio.wait_for(self._pkt_rec.wait(), rx_time)
            except asyncio.TimeoutError:
                self._do_stats(S_RX_TIMEOUTS)  # Loop again to retransmit pkt.
            else:  # Pkt was received so last was acknowledged. Create the next one.
                self._txq = self._txpkt.update(self._txq)
                self._is_running = True  # Start gathering stats now

    # A packet is ready. Any response implies an ACK: slave never transmits
    # unsolicited messages
    def _process_packet(self):
        rxdata, _, dupe, pwrup = self._rxpkt(self._radio.recv())
        if pwrup:  # Slave has had a power outage
            self._rxq = b''
        self._tlast = ticks_ms()  # User outage detection
        self._pkt_rec.set()
        if rxdata:  # Packet has data. ACK even if a dupe.
            self._do_stats(S_RX_ALL)  # Optionally count instances
            self._txcmd = ACK
            if not dupe:  # Add new packets to receive queue
                self._do_stats(S_RX_DATA)
                self._rxq = b''.join((self._rxq, rxdata))

class Slave(AS_NRF24L01):
    def __init__(self, config):
        super().__init__(config)
        self._listen(True)
        self._is_running = True  # Start gathering stats immediately

    def _process_packet(self):
        rxdata, rxcmd, dupe, pwrup = self._rxpkt(self._radio.recv())
        if pwrup:  # Master has had a power outage
            self._rxq = b''
        self._tlast = ticks_ms()
        if rxdata:
            self._do_stats(S_RX_ALL)  # Optionally count instances
            if not dupe:  # New data received.
                self._do_stats(S_RX_DATA)
                self._rxq = b''.join((self._rxq, rxdata))
        # If last packet was empty or was acknowledged, get next one.
        if (rxcmd == ACK) or not self._txpkt:
            self._txq = self._txpkt.update(self._txq)  # Replace txq
        asyncio.create_task(self._send(self._txpkt(MSG)))
        # Issues start_listening when done.
