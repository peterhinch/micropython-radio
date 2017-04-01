# async_radio_pickle
# A protocol for exchanging arbitrary Python objects between a pair of nRF24L01+ radios
# Uses uasyncio to achieve nonblocking behaviour (at the expense of speed).

import pyb, pickle, utime, gc
import uasyncio as asyncio
from micropython import const
from nrf24l01 import NRF24L01, POWER_3, SPEED_250K

COMMAND = const(0)                              # Byte 0 of message is command
BYTECOUNT = const(1)                            # Count of data bytes
MSGSTART = const(2)
PAYLOAD_SIZE = const(32)
MAXLEN = const(30)                              # Space left for data

OK = const(1)                                   # Commands
RESEND = const(2)
BYE = const(3)
START_SLAVE = const(4)
TXDONE = const(0x20)                            # Bit set for last message
MASK = const(0xdf)


class RadioSetup(object):                       # Configuration for an nRF24L01 radio
    channel = 99                                # Necessarily shared by both instances
    def __init__(self, *, spi_no, csn_pin, ce_pin):# May differ
        self.spi_no = spi_no
        self.ce_pin = ce_pin
        self.csn_pin = csn_pin


class CommandException(OSError):                # Unexpected command received
    pass
class Success(Exception):                       # Bail out because of successful completion
    pass
class NoData(Exception):                        # Slave raises it if master has sent npothing
    pass


class TxMessage(object):
    def __init__(self):
        self.outbuf = bytearray(32)             # Buffer with 4 data bytes followed by message
        self.msgbytes = None                    # bytes object holding message to send
        self.txleft = 0                         # No of bytes still to send
        self.offset = 0                         # offset into msgbytes
        self.bytes_tx = 0                       # message length of current transmission

    def initialise(self, objsend):              # Init with an object for transmission
        self.msgbytes = pickle.dumps(objsend).encode('utf8')
        self.txleft = len(self.msgbytes)
        self.offset = 0
        self.bytes_tx = 0
  
    def create_msg(self):                       # Populate buffer with a fragment
        bytes_tx = min(self.txleft, MAXLEN)     # No. of bytes to send this time
        if bytes_tx:                            # If there are any, copy to output buffer
            self.outbuf[MSGSTART : MSGSTART + bytes_tx] = self.msgbytes[self.offset : self.offset + bytes_tx]
        self.bytes_tx = bytes_tx

    def next_msg(self):                         # set up next message
        self.offset += self.bytes_tx            # add no of bytes sent
        self.txleft -= self.bytes_tx
        return self.txleft <= 0                 # True if last packet

    async def sendbuf(self, radio, cmd):
        radio.stop_listening()                  # Flush buffers
        start_time = pyb.millis()
        self.outbuf[COMMAND] = cmd
        if cmd == RESEND or cmd == BYE:         # Bye and Resend request have no data
            self.outbuf[BYTECOUNT] = 0
        else:
            self.outbuf[BYTECOUNT] = self.bytes_tx
            if self.txleft == 0:
                self.outbuf[COMMAND] |= TXDONE
        sent = False
        while not sent:
            await asyncio.sleep(0)
            try:
                await radio.as_send(self.outbuf)
                sent = True
            except OSError:                     # send timed out.
                pass                            # It may have returned early. Try again if so.
            finally:
                if pyb.elapsed_millis(start_time) >= radio.timeout:
                    radio.start_listening()
                    raise OSError
        radio.start_listening()


class TwoWayRadio(NRF24L01):
    pipes = (b'\xf0\xf0\xf0\xf0\xe1', b'\xf0\xf0\xf0\xf0\xd2')
    max_resend_requests = 1                     # No. of times receiver requests retransmission
    bye_no = 1                                  # No. of times BYE is sent
    timeout = 300                               # No. of mS tx and rx wait for each other
    def __init__(self, master, config):
        super().__init__(pyb.SPI(config.spi_no), pyb.Pin(config.csn_pin), pyb.Pin(config.ce_pin), config.channel, PAYLOAD_SIZE)
        if master:
            self.open_tx_pipe(TwoWayRadio.pipes[0])
            self.open_rx_pipe(1, TwoWayRadio.pipes[1])
        else:
            self.open_tx_pipe(TwoWayRadio.pipes[1])
            self.open_rx_pipe(1, TwoWayRadio.pipes[0])
        self.set_power_speed(POWER_3, SPEED_250K) # Best range for point to point links
        self.start_listening()
        self.txmsg = TxMessage()                # Data for transmission
        self.inlist = []                        # List of received bytes objects

    # nonblocking wait for tx complete. Note default args can't be bound to self.
    async def as_send(self, buf, timeout=-1):
        if timeout == -1:
            timeout = self.timeout
        send_nonblock = self.send_start(buf)
        start = pyb.millis()
        result = None
        while result is None and pyb.elapsed_millis(start) < timeout:
            await asyncio.sleep(0)
            result = self.send_done() # 1 == success, 2 == fail (None == in progress)
        if result == 2:
            raise OSError("send failed")

    def start_protocol(self, objsend):
        self.txmsg.initialise(objsend)
        self.inlist = []

    def get_latest_msg(self):
        inbuf = None
        while self.any():                       # Immediate return of None if nothing pending
            inbuf = self.recv()
        return inbuf

    async def await_message(self, allowed_cmds):
        start_time = pyb.millis()
        while True:
            await asyncio.sleep(0)
            if self.any():
                break
            if pyb.elapsed_millis(start_time) > self.timeout:
                raise OSError                   # Timeout
        inbuf = self.get_latest_msg()
        if inbuf is None or len(inbuf) < MSGSTART:
            raise OSError
        cmd = inbuf[0] & MASK
        if cmd not in allowed_cmds:
            raise CommandException              # Unexpected response
        nbytes = inbuf[BYTECOUNT]               # Received bytes
        if nbytes:                              # Can receive zero length messages (responses to tx)
            self.inlist.append(inbuf[MSGSTART: MSGSTART + nbytes].decode('utf8')) # List of received strings
        return inbuf[0], nbytes

    async def goodbye(self):
        self.stop_listening()
        self.txmsg.outbuf[COMMAND] = BYE
        self.txmsg.outbuf[BYTECOUNT] = 0
        for x in range(self.bye_no):
            await asyncio.sleep(0)
            try:
                await self.as_send(self.txmsg.outbuf, timeout = 20)
            except OSError:
                pass
        self.start_listening()

    async def run_protocol(self, rxdone, initcmd):  # initial cmd is START_SLAVE (master) or OK (slave)
        txdone = False
        while not (txdone and rxdone):          # Continue while there are bytes to send or receive
            sent = False
            self.txmsg.create_msg()
            send_cmd = initcmd
            resend_rq_count = 0                 # No.of resend requests sent
            while not sent:                     # Send and receive a message until success
                await self.txmsg.sendbuf(self, send_cmd)
                try:                            # Send the output buffer until success
                    cmd_raw, bytes_rx = await self.await_message((OK, RESEND, BYE))
                    cmd = cmd_raw & MASK        # Clear TXDONE bit
                    if cmd == BYE:              # Normal end to protocol: target has sent BYE
                        raise Success           # no response is required. Quit protocol.
                    sent = cmd == OK            # neither we nor the slave timed out
                except OSError:                 # We timed out waiting for message: request retransmission
                    if resend_rq_count > self.max_resend_requests:
                        if rxdone:              # transmission presumed to have failed but we got our data
                            raise Success       # Treat as success and let target sort out problem
                        else:
                            raise               # Target inaccessible: abandon
                    resend_rq_count += 1
                    send_cmd = RESEND           # with a zero length message
                else:                           # If slave requested retransmission we loop again
                    send_cmd = OK               # prepare for it in case we do: we repeat the data with OK
            txdone = self.txmsg.next_msg()
            rxdone = cmd_raw & TXDONE
            if txdone and rxdone:
                await self.goodbye()            # Over and out: no response expected


class Radio(TwoWayRadio):
    def __init__(self, config, master):
        super().__init__(master, config)
        self._master = master

    async def exchange(self, objtx=None):       # Caller polls this and (typically) ignores NoData
        self.start_protocol(objtx)              # Initialise the overall timeout and TxMessage object
        if self._master:
            try:
                await self.run_protocol(rxdone = False, initcmd = START_SLAVE)
            except Success:                     # Slave has signalled completion
                pass
            finally:
                self.stop_listening()           # Flush buffers prior to another run. Master doesn't listen.
        else:
            ok = False
            try:
                cmd, bytes_rx = await self.await_message((START_SLAVE,)) # Initial message: cmd should be START_SLAVE
                ok = True
            except CommandException:            # Occurs harmlessly when we pick up a BYE from
                pass                            # previous transfer.
            if not ok:                          # Try again. If this fails caller handles exception
                cmd, bytes_rx = await self.await_message((START_SLAVE,))
            try:
                await self.run_protocol(rxdone = cmd & TXDONE > 0, initcmd = OK) # Pass rxdone if master set TXDONE
            except Success:                     # Master has signalled completion
                pass                            # Other exceptions are handled by caller
        strpickle = ''.join(self.inlist)        # No exceptions: handle result
        objrx = pickle.loads(strpickle)
        return objrx


class Channel():
    latency_ms = 1000
    def __init__(self, config, master, *, txcb = lambda : None, rxcb = None, statecb = lambda _ : None):
        self._radio = Radio(config, master)
        self._master = master
        self._txdata = None
        self._rxdata = None
        self._txcb = txcb
        self._rxcb = rxcb
        self._statecb = statecb
        self._link_is_up = False
        loop = asyncio.get_event_loop()
        loop.create_task(self._run())
        loop.create_task(self._garbage_collect())

    async def _run(self):
        while True:
            try:
                self._rxdata = await self._radio.exchange(self._txdata)
                if not self._link_is_up:
                    self._statecb(True)
                self._link_is_up = True
            except NoData:  # Received an empty message: link is OK
                if not self._link_is_up:
                    self._statecb(True)
                self._link_is_up = True
            except CommandException:
                print('Command exception')  # debug
            except OSError:  # A timeout occurred
                self._link_is_up = False
                self._statecb(False)
            if self._link_is_up:  # A message was received so ours was sent
                if self._txdata is not None:
                    self._txdata = None
                    self._txcb()  # User may supply data if available
                if self._rxdata is not None and self._rxcb is not None:
                    self._rxcb(self._rxdata)
                    self._rxdata = None

            tstart = utime.ticks_ms()  # Master pauses between transmissions
            if self._master:
                while utime.ticks_diff(utime.ticks_ms(), tstart) < self.latency_ms:
                    await asyncio.sleep_ms(0)
                    if self._txdata is not None:  # User has called send()
                        break
            else:  # Slave waits for message from master
                while not self._radio.any():
                    await asyncio.sleep_ms(0)

    def txready(self):
        return self._txdata is None

    def send(self, data):
        if self._txdata is None:
            self._txdata = data
            return True
        return False

    def up(self):
        return self._link_is_up

    async def _garbage_collect(self):
        led = pyb.LED(2)
        while True:
            led.toggle()
            await asyncio.sleep_ms(500)
            gc.collect()
            gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
