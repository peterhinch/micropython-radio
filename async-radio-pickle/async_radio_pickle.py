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
        self.outbuf = bytearray(PAYLOAD_SIZE)   # Buffer with 2 data bytes followed by message
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
        self.outbuf[COMMAND] = cmd
        if cmd == RESEND or cmd == BYE:         # Bye and Resend request have no data
            self.outbuf[BYTECOUNT] = 0
        else:
            self.outbuf[BYTECOUNT] = self.bytes_tx
            if self.txleft == 0:
                self.outbuf[COMMAND] |= TXDONE

        start = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start) < radio.timeout:
            # On timeout returns None. On fail (2) or success (1) returns immediately.
            res = await radio.as_send(self.outbuf, timeout = radio.timeout)  # loop repeatedly on fail
            if res == 1:                        # Success.
                radio.start_listening()
                break
        else:                                   # Timeout
            print('Send fail', res)  # OCCURS QUITE FREQUENTLY
            radio.start_listening()
            raise OSError


class TwoWayRadio(NRF24L01):
    pipes = (b'\xf0\xf0\xf0\xf0\xe1', b'\xf0\xf0\xf0\xf0\xd2')
    max_resend_requests = 1                     # No. of times receiver requests retransmission
    timeout = 200                               # No. of mS tx and rx wait for each other
    def __init__(self, config, master):
        super().__init__(pyb.SPI(config.spi_no), pyb.Pin(config.csn_pin), pyb.Pin(config.ce_pin), config.channel, PAYLOAD_SIZE)
        self._master = master
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
        self.failcount = 0  # DEBUG

    # asynchronous send. Raises no errors: returns status. Waits for completion subject to timeout.
    # Return is immediate if result is success or failure.
    async def as_send(self, buf, timeout):
        self.send_start(buf)                    # Non blocking start TX
        start = utime.ticks_ms()
        result = None
        while result is None and utime.ticks_diff(utime.ticks_ms(), start) < timeout:
            await asyncio.sleep(0)
            result = self.send_done() # 1 == success, 2 == fail (None == in progress)
        return result

    def start_protocol(self, objsend):
        self.txmsg.initialise(objsend)
        self.inlist = []

    def get_latest_msg(self):
        inbuf = None
        while self.any():                       # Immediate return. False if nothing pending.
            inbuf = self.recv()
        return inbuf

    async def await_message(self, allowed_cmds):
        start = utime.ticks_ms()
        while not self.any():
            if utime.ticks_diff(utime.ticks_ms(), start) > self.timeout:
                print('await_message T/O')
                raise OSError                   # Timeout
            await asyncio.sleep(0)

        inbuf = self.get_latest_msg()
        await asyncio.sleep(0)
        if inbuf is None or len(inbuf) < MSGSTART:
            raise OSError
        cmd = inbuf[0] & MASK
        if cmd not in allowed_cmds:
            raise CommandException(cmd,  allowed_cmds)         # Unexpected response
        nbytes = inbuf[BYTECOUNT]               # Received bytes
        if nbytes:                              # Can receive zero length messages (responses to tx)
            self.inlist.append(inbuf[MSGSTART: MSGSTART + nbytes].decode('utf8')) # List of received strings
        return inbuf[0], nbytes

    async def goodbye(self):
        self.stop_listening()
        self.txmsg.outbuf[COMMAND] = BYE
        self.txmsg.outbuf[BYTECOUNT] = 0
        await self.as_send(self.txmsg.outbuf, timeout = 20)  # return: don't care about failure
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
                    send_cmd = RESEND           # Request resend (with a zero length message)
                else:                           # If slave requested retransmission we loop again
                    send_cmd = OK               # prepare for it in case we do: we repeat the data with OK
            txdone = self.txmsg.next_msg()
            rxdone = cmd_raw & TXDONE
            if txdone and rxdone:
                await self.goodbye()            # Over and out: no response expected

    async def exchange(self, objtx):            # Caller polls this and (typically) ignores NoData
        self.start_protocol(objtx)              # Initialise the overall timeout and TxMessage object
        if self._master:
            try:
                await self.run_protocol(rxdone = False, initcmd = START_SLAVE)
            except Success:                     # Slave has signalled completion
                pass
            finally:
                self.stop_listening()           # Flush buffers prior to another run. Master doesn't listen.
        else:
            cmd, bytes_rx = await self.await_message((START_SLAVE,)) # Initial message: cmd should be START_SLAVE
            try:
                await self.run_protocol(rxdone = cmd & TXDONE > 0, initcmd = OK) # Pass rxdone if master set TXDONE
            except Success:                     # Master has signalled completion
                pass                            # Other exceptions are handled by caller
        strpickle = ''.join(self.inlist)        # No exceptions: handle result
        try:
            objrx = pickle.loads(strpickle)
        except:  # NameError (Exception subclass)
            self.failcount += 1  # DEBUG
            raise OSError                       # Treat as a timeout. Protocol recovers.
        return objrx


class Channel():
    _error_pause_ms = 2000
    def __init__(self, config, master, *, txcb = None, rxcb = None, statecb = None):
        self._radio = TwoWayRadio(config, master)
        self._master = master
        self._txdata = None
        self._rxdata = None
        self._txcb = txcb  # User callbacks
        self._rxcb = rxcb
        self._statecb = statecb
        self._link_is_up = False  # Ensure callback occurs when link activates
        loop = asyncio.get_event_loop()
        loop.create_task(self._run())
        loop.create_task(self._garbage_collect())
        loop.create_task(self.report())  # DEBUG

    async def _run(self):
        while True:
            pause_ms = 2000  # Assume success. 200 Allows for slave sending BYE
            abort = False
            try:
                self._rxdata = await self._radio.exchange(self._txdata)
                if self._statecb is not None and not self._link_is_up:
                    self._statecb(True)
                self._link_is_up = True
            except NoData:  # Received an empty message: link is OK
                if self._statecb is not None and not self._link_is_up:
                    self._statecb(True)
                self._link_is_up = True
            except CommandException as c:
                expected = c.args[1][0]
                got = c.args[0]
                # Ignore special case where we got the trailing end of previous message
                if not (expected == START_SLAVE and got == BYE):
                    print('Command exception', expected, got) # expected START_SLAVE got RESEND (2)
                    abort = True
            except OSError:  # A timeout occurred
                print('Timeout')
                abort = True
            if abort:
                if self._statecb is not None and self._link_is_up:
                    self._statecb(False)
                self._link_is_up = False
                if self._master:
                    pause_ms = self._error_pause_ms  # Hold off transmissions: slave may still be sending
            if self._link_is_up:  # A message was received so ours was sent
                if self._txdata is not None:
                    self._txdata = None
                    if self._txcb is not None:
                        self._txcb()  # User may supply data if available
                if self._rxdata is not None and self._rxcb is not None:
                    self._rxcb(self._rxdata)
                    self._rxdata = None

            tstart = utime.ticks_ms()  # In event of failure master pauses between transmissions
            if self._master:
                if pause_ms:
                    while utime.ticks_diff(utime.ticks_ms(), tstart) < pause_ms:
                        await asyncio.sleep_ms(0)
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

    async def report(self):  # DEBUG
        while True:
            print('Fail count: ', self._radio.failcount)
            await asyncio.sleep(60)
