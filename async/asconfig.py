# Config data for your hardware: adapt as required.
from machine import SPI, Pin
# config file instantiates a RadioSetup for each end of the link
class RadioSetup:  # Configuration for an nRF24L01 radio
    channel = 97  # Necessarily shared by both instances
    tx_ms = 200  # Max ms either end waits for successful transmission

    def __init__(self, spi, csn, ce, stats=False):
        self.spi = spi
        self.csn = csn
        self.ce = ce
        self.stats = stats

# Note: gathering statistics. as_nrf_test will display them.
config_testbox = RadioSetup(SPI(1), Pin('X5'), Pin('Y11'), True)  # My testbox
config_v1 = RadioSetup(SPI(1), Pin('X5'), Pin('X4'), True)  # V1 Micropower PCB
config_v2 = RadioSetup(SPI(1), Pin('X5'), Pin('X2'), True)  # V2 Micropower PCB with SD card
config_master = config_v1
config_slave = config_v2
