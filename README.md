# Curiosity_CircuitPython_dev_board_test_suite
Test suite for Curiosity CircuitPython dev board

This test suite tests the following hardware & peripherals:
- Onboard LED
- NeoPixel
- GPIO Pin Pair tests
- RNBD451 BLE echo
- LED GPIOs
- CAN bus loopback and bus
- Cap Touch button
- SPI bus for TFT display on Ruler
- Analog out "Breathing LED" on DAC
- Debug UART
- ADC input sweep
- SPI bus for SD Card on Ruler
- I2C bus

This test code is based on Shawn Hymel's boardtest suite:
https://github.com/adafruit/Adafruit_CircuitPython_BoardTest
but greatly expands on it to provide tests specific to the 
Microchip Curiosity CircuitPython dev board.
