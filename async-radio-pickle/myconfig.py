# Config data for your hardware: adapt as required. Can also set rp.RadioSetup.channel
import async_radio_pickle as rp
config_testbox = rp.RadioSetup(spi_no = 1, csn_pin = 'X5', ce_pin = 'Y11')   # My testbox
config_v1 = rp.RadioSetup(spi_no = 1, csn_pin = 'X5', ce_pin = 'X4')     # V1 Micropower PCB
config_v2 = rp.RadioSetup(spi_no = 1, csn_pin = 'X5', ce_pin = 'X2')        # V2 Micropower PCB
