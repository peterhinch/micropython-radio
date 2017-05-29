# async_radio_pickle
# A protocol for exchanging arbitrary Python objects between a pair of nRF24L01+ radios
# Uses uasyncio to achieve nonblocking behaviour (at the expense of speed).

import pyb
import pickle
import gc
import uasyncio as asyncio
from micropython import const
from nrf24l01 import NRF24L01, POWER_3, SPEED_250K

def dolittle(*_):                               # Null callback lambda *_ : None
    pass

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

async def _garbage_collect():
    while True:
        await asyncio.sleep_ms(500)
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())


class TxQueue():                                # Transmit queue returns the default
    def __init__(self, size):                   # transmit object (None) if no data.
        self.size = size
        self.q =[]

    def put(self, data):
        if not self.txrdy():
            return False
        self.q.append(data)
        return True

    def get(self):
        if len(self.q):
            return self.q.pop(0)

    def txrdy(self):
        return len(self.q) < self.size


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
  
    def create_msg_block(self):                 # Populate buffer with a fragment
        bytes_tx = min(self.txleft, MAXLEN)     # No. of bytes to send this time
        if bytes_tx:                            # If there are any, copy to output buffer
            self.outbuf[MSGSTART : MSGSTART + bytes_tx] = self.msgbytes[self.offset : self.offset + bytes_tx]
        self.bytes_tx = bytes_tx

    def next_msg(self):                         # set up next message
        self.offset += self.bytes_tx            # add no of bytes sent
        self.txleft -= self.bytes_tx
        return self.txleft <= 0                 # True if last packet

    def set_cmd(self, cmd):                     # Prepare message for transmission
        self.outbuf[COMMAND] = cmd              # Bye and Resend request have no data
        self.outbuf[BYTECOUNT] = 0 if cmd == RESEND or cmd == BYE else self.bytes_tx
        if self.txleft <= MAXLEN:
            self.outbuf[COMMAND] |= TXDONE


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

    # Asynchronous send. Raises no errors: returns status. Waits for completion subject to timeout.
    # Return is immediate if result is success or failure.
    async def as_send(self, timeout=None):
        self.send_start(self.txmsg.outbuf)      # Non blocking start TX
        if timeout is None:
            timeout = self.timeout
        for _ in range(max(timeout // 10, 1)):
            await asyncio.sleep_ms(10)
            result = self.send_done()           # 1 == success, 2 == fail (None == in progress)
            if result is not None:
                break
        self.start_listening()
        return result

    # Asynchronously send a message block
    async def send_msg_block(self, cmd):
        self.stop_listening()                   # Flush buffers
        self.txmsg.set_cmd(cmd)                 # Prepare message block for transmission
        res = await self.as_send()              # Attempt to send
        return res == 1                         # False on fail or timeout.
        #start = utime.ticks_ms()
        #while utime.ticks_diff(utime.ticks_ms(), start) < self.timeout:
            ## On timeout as_send() returns None. On fail (2) or success (1) returns immediately.
            #res = await self.as_send()          # loop repeatedly on fail
            #if res == 1:                        # Success.
                #self.start_listening()
                #break
            #if res == 2:
                #await asyncio.sleep_ms(self.timeout // 5)  # Possible RF interference?
        #else:                                   # Timeout
            #self.start_listening()
            #return False
        #return True

    def parse(self):
        strpickle = ''.join(self.inlist)
        if strpickle:                           # data was sent
            return pickle.loads(strpickle)      # Throws exception on fail

# Wait for a message. If forever (i.e. slave waiting for START_SLAVE) blocks until msg received.
# Returns command received or 0 on failure
    async def await_message(self, allowed_cmds, forever=False, rxdone=False):
        iterations = self.timeout // 10
        while not self.any():
            if not forever:
                if iterations <= 0:
                    return 0
                iterations -= 1
            await asyncio.sleep_ms(10)

        while self.any():                       # Discard all but latest message
            inbuf = self.recv()
            await asyncio.sleep_ms(10)

        if inbuf is None or len(inbuf) < MSGSTART:
            return 0
        cmd = inbuf[0] & MASK
        if cmd not in allowed_cmds:
            return 0                            # Unexpected response
        nbytes = inbuf[BYTECOUNT]               # Received bytes
        if nbytes and not rxdone:               # Can receive zero length messages (responses to tx)
            self.inlist.append(inbuf[MSGSTART: MSGSTART + nbytes].decode('utf8')) # List of received strings
        return inbuf[0]

    async def goodbye(self):                    # Send BYE. No exceptions raised. No RX expected.
        self.stop_listening()
        self.txmsg.set_cmd(BYE)
        await self.as_send(timeout = 20)        # return: don't care about failure
        self.start_listening()

    # Core protocol. Returns status, data.
    # On error - timeout or parse failure - returns False, None
    # Success returns True, received object which may be None.
    async def run_protocol(self):
        txdone = False
        rxdone = False
        if self._master:
            self.inlist = []                    # Master: initialise RX
            send_cmd = START_SLAVE
        else:                                   # Slave waits for master discarding messages. It
            started = False                     # send nothing until it gets START_SLAVE
            while not started:
                self.inlist = []                # Discard any previous bad message
                cmd_raw = await self.await_message((START_SLAVE,), forever=True)
                if cmd_raw:
                    started = True
            rxdone = cmd_raw & TXDONE
            send_cmd = OK                       # Always send OK before no data BYE command
                                                # Symmetrical from here
        while not (txdone and rxdone):          # Continue while there are bytes to send or receive
            self.txmsg.create_msg_block()
            resend_rq_count = 0                 # No.of resend requests sent: reset for each block
            cmd = 0
            cmd_raw = 0
            sent = False
            while not sent:                     # Send and receive a message block until success
                if not await self.send_msg_block(send_cmd):  # Timeout handled by caller
                    return False, None
                while resend_rq_count <= self.max_resend_requests:  # Send the output buffer until success
                    await asyncio.sleep_ms(10)
                    cmd_raw = await self.await_message((OK, RESEND, BYE), rxdone)  # rxdone handles case where BYE missed
#                    print('Await with rxdone = ', rxdone, 'got', cmd_raw)
                    if not cmd_raw:
                        resend_rq_count += 1
                        send_cmd = RESEND       # Request resend (with a zero length message)
                        continue

                    cmd = cmd_raw & MASK        # Clear TXDONE bit
                    if cmd == BYE:              # Normal end to protocol: target has sent BYE
#                        print('Success. BYE received. Inlist:', self.inlist)
                        try:                    # no response is required. Quit protocol.
                            return True, self.parse()
                        except:                 # Parse fail. Should never occur.
#                            print('Parse fail 1.')
                            self.failcount += 1 # DEBUG
                            return False, None
                    break                       # Got OK or RESEND
                else:                           # Retransmissions have failed
                    return False, None

                sent = cmd == OK                # neither we nor the slave timed out
                                                # If slave requested retransmission we loop again
                send_cmd = OK                   # prepare for it in case we do: we repeat the data with OK
            txdone = self.txmsg.next_msg()
            rxdone = rxdone or cmd_raw & TXDONE
#            print('Txdone: {} rxdone: {} inlist: {}'.format(txdone, rxdone, self.inlist))
        try:
            result = self.parse()
        except:
            #print('Parse fail 2.')
            self.failcount += 1 # DEBUG
            return False, None

        await self.goodbye()                    # Over and out: no response expected.
#        print('BYE sent.')
        return True, result

    async def exchange(self, objtx):
        self.txmsg.initialise(objtx)            # Set up TX message object
        status, objrx = await self.run_protocol()
        if not status:
            if self._master:
                self.stop_listening()           # Flush buffers. Master doesn't listen.
        return status, objrx


# TODO callback args
class Channel():
#    latency = 1000
    def __init__(self, config, master, *, txqsize=20,
                 txcb = dolittle, rxcb=dolittle, statecb=dolittle):
        self._radio = TwoWayRadio(config, master)
        self._master = master
        self._txq = TxQueue(txqsize)
        self._txcb = txcb                       # User callbacks
        self._rxcb = rxcb
        self._statecb = statecb
        self._link_is_up = False                # Ensure callback occurs when link activates
        loop = asyncio.get_event_loop()
        loop.create_task(self._run())
        loop.create_task(_garbage_collect())

    @property
    def link(self):
        return self._link_is_up

    @link.setter
    def link(self, value):
        if self._link_is_up != value:
            self._statecb(value)
        self._link_is_up = value

    async def _run(self):
        radio = self._radio
        msg_delay = 100                         # Normal delay between master messages (ms)
                                                # Worst-case time to allow for slave to time out
        error_delay = msg_delay + (radio.max_resend_requests + 1) * radio.timeout
        last_msg_sent = True                    # Status of last transmission
        txdata = None
        while True:
            rxdata = None
            if last_msg_sent:                   # Last TX was successful
                txdata = self._txq.get()        # Get new data or None.
                                                # duplicate messages if RX success not detected by sender
            status, rxdata = await radio.exchange(txdata)
            if status:
#                print('Sent: ', txdata)
                self._txcb()
                self.link = True
                if txdata is not None:          # Last message was sent correctly
                    last_msg_sent = True
            else:                               # A timeout or bad rx message occurred
#                print('Timeout or bad rx message.')
                self.link = False
                if txdata is not None:
                    last_msg_sent = False
#                print('Failed txdata: ', txdata)
#                print('Failed rxdata: ', rxdata)

            if rxdata is not None :
                self._rxcb(rxdata)
                rxdata = None

            if self._master:                    # Pause to allow slave to time out on error ?????
                delay = msg_delay if self.link else error_delay
                await asyncio.sleep_ms(delay)

    def txrdy(self):
        return self._txq.txrdy()

    def send(self, data):
        return self._txq.put(data)              # Return success status.
