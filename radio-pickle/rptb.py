# test using testbox with LCD for range testing
# On testbox run test()
# on V1 PCB run ts()
import pyb
import radio_pickle as rp
from usched import Sched, wait, Roundrobin
from lcdthread import LCD, PINLIST                          # Library supporting Hitachi LCD module
from myconfig import config_master, config_slave              # Configs for my hardware
# usched and lcdthread at https://github.com/peterhinch/Micropython-scheduler.git

def master(lcd):
    yield Roundrobin()
    m = rp.Master(config_master)
    obj = [0, '']
    x = ord('a')
    while True:
        start = pyb.millis()
        try:
            result = m.exchange(obj)
            t = pyb.elapsed_millis(start)
        except OSError:
            t = pyb.elapsed_millis(start)
            lcd[0] = 'Timeout'
        else:
            lcd[0] = str(result)
        finally:
            lcd[1] = 't = {}mS'.format(t)
        yield from wait(1.0)
        obj[0] += 1

# Run this on testbox, run ts() on slave
def test():
    objSched = Sched()
    lcd0 = LCD(PINLIST, objSched, cols = 24)
    objSched.add_thread(master(lcd = lcd0))
    objSched.run()

# test_master() and test_slave() run at REPL (master on testbox) to check a variety of
# message lengths including different lengths in each direction
def test_master():
    m = rp.Master(config_master)
    obj = [0, ''] # object to be sent
    x = ord('a')
    while True:
        try:
            result = m.exchange(obj)
        except OSError: # Optionally trap timeout errors (e.g. out of range)
            print("Timeout")
        else:
            print(result) # No errors raised
            if result[0] != len(result[1]):
                print('Error')
                break
        pyb.delay(1000) # send 1 message per sec
        obj[1] = obj[1] + chr(x) if len(obj[1]) < 71 else '' # Keep from getting too huge
        x = x +1 if x < ord('z') else ord('a')
        obj[0] = len(obj[1])

def test_slave():
    # for my hardware. Delete these three lines for normal h/w
    from micropower import PowerController
    power_controller = PowerController(pin_active_high = 'Y12', pin_active_low = 'Y11')
    power_controller.power_up()

    s = rp.Slave(config_slave)
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
            if result[0] != len(result[1]):
                print('Error')
                break
            obj[1] = obj[1] + chr(x) if len(obj[1]) < 70 else '' # Keep from getting too huge
            x = x +1 if x < ord('z') else ord('a')
            obj[0] = len(obj[1])

# Simple confidence checks
def tm():                                       # Test master. Runs on testbox
    m = rp.Master(config_master)
    obj = [0, '']
    x = ord('a')
    while True:
        try:
            result = m.exchange(obj)
        except OSError:
            print("Timeout")
        else:
            print(result)
        pyb.delay(1000)
        obj[0] += 1

def ts():                                       # Test slave: runs on V1 board
    from micropower import PowerController
    power_controller = PowerController(pin_active_high = 'Y12', pin_active_low = 'Y11')
    power_controller.power_up()
    s = rp.Slave(config_slave)
    obj = [0, '']
    x = ord('a')
    while True:
        try:
            result = s.exchange(obj)
        except rp.NoData:                          # Master has sent nothing
            pass
        except OSError:
            print("Timeout")
        else:
            print(result)
            obj[0] += 1
            obj[1] += chr(x)
            x = x +1 if x < ord('z') else ord('a')
            if len(obj[1]) > 12:
                obj[1] = ''         # Fit in LCD
