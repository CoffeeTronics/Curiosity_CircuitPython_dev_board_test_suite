# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
`BoardTest Suite`
====================================================
CircuitPython board hardware test suite
"""

import board
import time
import supervisor

# NEW: extra modules for resource teardown
import displayio
import digitalio
import microcontroller
import gc
from analogio import AnalogIn, AnalogOut

# NEW: safe no-input wrapper for non-interactive tests
class _NoInputCtx:
    """Temporarily replace builtins.input so tests don't block for Enter."""
    def __enter__(self):
        try:
            import builtins
            self._builtins = builtins
            self._had_input = hasattr(builtins, "input")
            if self._had_input:
                self._orig_input = builtins.input
                builtins.input = lambda *a, **k: ""
        except Exception:
            self._builtins = None
            self._had_input = False
        return self
    def __exit__(self, exc_type, exc, tb):
        try:
            if self._had_input and self._builtins is not None:
                self._builtins.input = self._orig_input
        except Exception:
            pass

from adafruit_boardtest import (
    boardtest_gpio,
    boardtest_i2c,
    boardtest_led,
    boardtest_spi,
    boardtest_uart,
    boardtest_voltage_monitor,
    boardtest_analog_out,
    boardtest_can,
    boardtest_neopixel,
    boardtest_cap_touch,
    boardtest_move_board,
    boardtest_pin_group_tester,
    boardtest_dac_adc,
    boardtest_ble_uart,
    boardtest_display_sprite_text as boardtest_display,  # display test lib
)

supervisor.runtime.autoreload = False

# ------------------------------- Constants -------------------------------
UART_TX_PIN_NAME = "DEBUG_TX"
UART_RX_PIN_NAME = "DEBUG_RX"
UART_BAUD_RATE = 9600

SPI_MOSI_PIN_NAME = "SD_MOSI"
SPI_MISO_PIN_NAME = "SD_MISO"
SPI_SCK_PIN_NAME  = "SD_SCK"
SPI_CS_PIN_NAME   = "SD_CS"

I2C_SDA_PIN_NAME = "SDA"
I2C_SCL_PIN_NAME = "SCL"

DAC_PIN_NAME = "DAC"

CAN_TX_PIN_NAME = "CAN_TX"
CAN_RX_PIN_NAME = "CAN_RX"
CAN_BAUD_RATE   = 250_000
CAN_STANDBY_PIN_NAME = "CAN_STANDBY"

NEOPIXEL_DATA_PIN_NAME = "NEOPIXEL"   # or a D-pin like "D6" for an external strip
NEOPIXEL_COUNT = 1

CAP_TOUCH_PIN_NAME = "CAP1"           # adjust to your wiring
LED_PIN_NAME       = "LED"

# ------------------------------- Results -------------------------------
TEST_RESULTS = {}     # name -> status string
PINS_TESTED  = []     # list of lists (plain pin names)

# ----------------------------- Helpers -----------------------------
def _breather():
    gc.collect()
    time.sleep(0.02)

# In code.py, replace _free_display_everything() with:

def _free_display_everything():
    import gc, time, digitalio
    try:
        displayio.release_displays()
    except Exception:
        pass
    # free common control pins used by the TFT on your rig
    for name in ("D13", "LCD_CS"):
        try:
            dio = digitalio.DigitalInOut(getattr(board, name))
            dio.direction = digitalio.Direction.INPUT
            try:
                dio.pull = None
            except Exception:
                pass
            dio.deinit()
        except Exception:
            pass
    # attempt to close the LCD SPI once displays are released
    try:
        spi = board.LCD_SPI()
        try:
            spi.deinit()
        except Exception:
            pass
    except Exception:
        pass
    gc.collect()
    time.sleep(0.03)


def _free_resources_for_dac_adc():
    def _free_pin(name):
        if hasattr(board, name):
            try:
                dio = digitalio.DigitalInOut(getattr(board, name))
                dio.deinit()
            except Exception:
                pass
    for name in ("A0","A1","A2","A3","A4","A5","DAC","SDA","SCL"):
        _free_pin(name)
    gc.collect(); time.sleep(0.02)

def _fmt_list(lst):
    return ", ".join(lst) if lst else "None"

# Helpers to free BLE pins cleanly
def _pulse_ble_reset(active_low=True, ms=50, settle_ms=300):
    import digitalio
    pin = getattr(board, "BLE_CLR", None)
    if not pin:
        return
    dio = digitalio.DigitalInOut(pin)
    dio.direction = digitalio.Direction.OUTPUT
    # idle
    dio.value = True if active_low else False
    time.sleep(0.01)
    # pulse
    dio.value = False if active_low else True
    time.sleep(ms/1000.0)
    # idle and settle
    dio.value = True if active_low else False
    dio.deinit()
    time.sleep(settle_ms/1000.0)

def _free_ble_pins():
    import digitalio
    for name in ("BLE_TX", "BLE_RX"):
        pin = getattr(board, name, None)
        if not pin:
            continue
        try:
            dio = digitalio.DigitalInOut(pin)
            # Put pad in a benign state, then release
            dio.direction = digitalio.Direction.INPUT
            try:
                dio.pull = None
            except Exception:
                pass
            dio.deinit()
        except Exception:
            pass
    # Small settle + GC
    gc.collect()
    time.sleep(0.02)

# ----------------------------- Banner / Pin list -----------------------------
print()
print("**********************************************************************")
print("*           Welcome to the CircuitPython board test suite!           *")
print("*              Follow the directions to run each test.               *")
print("**********************************************************************")
print()

PINS = list(dir(board))
print("All pins found:", end=" ")
for pin in PINS:
    print(pin, end=" ")
print("\n")

# --------------------------------- Tests ---------------------------------

# LED (interactive)
print("@)}---^-----  LED TEST  -----^---{(@)")
RESULT = boardtest_led.run_test(PINS)
TEST_RESULTS["LED Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# GPIO (interactive)
print("@)}---^-----  GPIO TEST  -----^---{(@)")
RESULT = boardtest_gpio.run_test(PINS)
TEST_RESULTS["GPIO Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# NEOPIXEL (interactive)
print("@)}---^-----  NEOPIXEL TEST  -----^---{(@)")
RESULT = boardtest_neopixel.run_test(
    PINS, NEOPIXEL_DATA_PIN_NAME, NEOPIXEL_COUNT, 0.2, (1, 0, 2, 3)
)
TEST_RESULTS["NeoPixel Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# UART (NON-interactive)
print("@)}---^-----  UART TEST  -----^---{(@)")
with _NoInputCtx():
    RESULT = boardtest_uart.run_test(PINS, UART_TX_PIN_NAME, UART_RX_PIN_NAME, UART_BAUD_RATE)
TEST_RESULTS["UART Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# SPI (NON-interactive)
print("@)}---^-----  SPI TEST  -----^---{(@)")
with _NoInputCtx():
    RESULT = boardtest_spi.run_test(
        PINS,
        mosi_pin=SPI_MOSI_PIN_NAME,
        miso_pin=SPI_MISO_PIN_NAME,
        sck_pin=SPI_SCK_PIN_NAME,
        cs_pin=SPI_CS_PIN_NAME,
    )
TEST_RESULTS["SPI Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# I2C (NON-interactive)
print("@)}---^-----  I2C TEST  -----^---{(@)")
with _NoInputCtx():
    RESULT = boardtest_i2c.run_test(PINS, sda_pin=I2C_SDA_PIN_NAME, scl_pin=I2C_SCL_PIN_NAME)
TEST_RESULTS["I2C Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# Analog Out (interactive "breathing LED")
print("@)}---^-----  ANALOG OUT TEST  -----^---{(@)")
RESULT = boardtest_analog_out.run_test(PINS, dac_pin=DAC_PIN_NAME)
TEST_RESULTS["Analog Out - 'Breathing' LED Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# CAN (NON-interactive: loopback)
print("@)}---^-----  CAN TEST  -----^---{(@)")
with _NoInputCtx():
    RESULT = boardtest_can.run_test(
        PINS, CAN_TX_PIN_NAME, CAN_RX_PIN_NAME, CAN_BAUD_RATE,
        0x408, CAN_STANDBY_PIN_NAME, loopback=True, num_frames=3, recv_timeout=0.9,
    )
TEST_RESULTS["CAN Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# Move board prompt (interactive)
print("Move dev board to lower section on breadboard test rig")
print("@)}---^-----  MOVE BOARD  -----^---{(@)")
RESULT = boardtest_move_board.run_test(PINS, "LOWER section")
TEST_RESULTS["Move Board"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
print("\n" + RESULT[0] + "\n")
_breather()

# Capacitive Touch (interactive)
print("@)}---^-----  CAPACITIVE TOUCH BUTTON TEST  -----^---{(@)")
RESULT, PINS_USED = boardtest_cap_touch.run_test(
    PINS, CAP_TOUCH_PIN_NAME, LED_PIN_NAME,
    touch_timeout_s=10.0, release_timeout_s=10.0, poll_interval_s=0.02,
)
TEST_RESULTS["Capacitive Touch Button Test"] = RESULT
PINS_TESTED.append(PINS_USED)
print(f"\nCapacitive Touch Button Test: {RESULT}")
print("Pins tested:", PINS_USED, "\n")
_breather()


# --- BLE UART ECHO TEST (run before GPIO/pin-group) ---
print("@)}---^-----  BLE UART ECHO TEST  -----^---{(@)")
# Make sure the pads are free and the module is quiet
_free_ble_pins()
_pulse_ble_reset(active_low=True, ms=40, settle_ms=150)

_result = boardtest_ble_uart.run_test(
    PINS,
    baudrate=115200,
    connect_timeout_s=10,     # short connect wait; we accept any RX as link
    user_timeout_s=120,
    active_state_query=False, # do not spam AT+STATE? in transparent mode
    do_reset=False,           # we already pulsed reset above (optional)
    reset_active_low=True,
    quiet_shutdown=True,      # driver will hold module in reset before deinit
    quiet_hold_ms=150,
)

# Unpack & summarize safely (bounded text already in the driver)
if isinstance(_result, tuple) and len(_result) == 3:
    STATUS, PINS_USED, INFO = _result
else:
    STATUS, PINS_USED = _result
    INFO = {"received": ""}

rx = INFO.get("received", "") or ""
TEST_RESULTS["BLE UART Echo Test"] = STATUS + (f' | RX="{rx}"' if rx else "")
PINS_TESTED.append(PINS_USED)
print(f'BLE UART Echo Test: {TEST_RESULTS["BLE UART Echo Test"]}')
print("Pins tested:", PINS_USED)
print()

# Extra belt & suspenders: free the pads again in case the module is chatty
_free_ble_pins()
gc.collect()
time.sleep(0.03)

# Run Pin Group Tests - Write & Read (exclude BLE pins so D0/D1 aren’t re-grabbed)
print("\n@)}---^-----  DIGITAL PIN WRITE / READ TEST  -----^---{(@)")
PIN_GROUP_SET = [p for p in PINS if p not in ("BLE_TX", "BLE_RX", "BLE_CLR")]
RESULT = boardtest_pin_group_tester.run_test(PIN_GROUP_SET, cycles=3, step_delay=0.1)
print(f"Pin Pair Test: {RESULT[0]}")
print("Pins tested:", RESULT[1])
TEST_RESULTS["Pin Pair Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])

'''
# Digital Pin Write/Read (NON-interactive) — pass a SAFE list
print("\n@)}---^-----  DIGITAL PIN WRITE / READ TEST  -----^---{(@)")
RESERVED = {
    "SDA","SCL","NEOPIXEL","LED","CAN_TX","CAN_RX","D13",
    "QSPI_CS","QSPI_SCK","QSPI_IO0","QSPI_IO1","QSPI_IO2","QSPI_IO3",
    "SD_MOSI","SD_MISO","SD_SCK","SD_CS", "D13"
}
SAFE_PINS = [p for p in PINS if p not in RESERVED]
with _NoInputCtx():
    RESULT = boardtest_pin_group_tester.run_test(SAFE_PINS, cycles=3, step_delay=0.1)
print(f"Pin Pair Test: {RESULT[0]}")
print("Pins tested:", RESULT[1])
TEST_RESULTS["Pin Pair Test"] = RESULT[0]
PINS_TESTED.append(RESULT[1])
_breather()
'''

# DAC/ADC sweep (NON-interactive)
print("\n@)}---^-----  DAC/ADC SWEEP TEST  -----^---{(@)")
_free_resources_for_dac_adc()
with _NoInputCtx():
    status, pins_used, details = boardtest_dac_adc.run_test(
        PINS, step=4096, dwell=0.005, repeats=1, verbose=False, require_all_inputs=True,
    )
detail = ""
if isinstance(details, dict):
    out_pin   = details.get("output")
    pass_list = _fmt_list(details.get("pass", []))
    fail_list = _fmt_list(details.get("fail", []))
    detail = f" | OUT={out_pin} PASS=[{pass_list}] FAIL=[{fail_list}]"
TEST_RESULTS["DAC/ADC Sweep Test"] = status + detail
PINS_TESTED.append(pins_used)
print(f"DAC/ADC Sweep Test: {status}")
print("Pins tested:", pins_used)
print()
_breather()

# Display sprite/text (interactive) — cleans up internally
print("@)}---^-----  DISPLAY SPRITE/TEXT TEST  -----^---{(@)")
try:
    RESULT = boardtest_display.run_test(
        PINS, vx=1, vy=1, frame_delay=0.04, motion_prompt_delay_s=1.0, prompt_timeout_s=None
    )
    TEST_RESULTS["Display Sprite/Text Test"] = RESULT[0]
    PINS_TESTED.append([])
    print(f"Display Sprite/Text Test: {RESULT[0]}")
    print("Info:", RESULT[1])
    print()
finally:
    _free_display_everything()
    _free_resources_for_dac_adc()
    _breather()





# ------------------------------ Summary --------------------------------
print("@)}---^-----  TEST RESULTS  -----^---{(@)\n")
NUM_SPACES = max((len(k) for k in TEST_RESULTS), default=0)
for key, val in TEST_RESULTS.items():
    print(key + ":", end=" ")
    for _ in range(NUM_SPACES - len(key)):
        print(end=" ")
    print(val)
print()

TESTED = []
for entry in PINS_TESTED:
    if isinstance(entry, (list, tuple, set)):
        TESTED.extend(list(entry))
    elif isinstance(entry, str):
        TESTED.append(entry)
NOT_TESTED = list(set(PINS).difference(set(TESTED)))

print("The following pins were tested:", end=" ")
for pin in TESTED:
    print(pin, end=" ")
print("\n")

print("The following pins were NOT tested:", end=" ")
for pin in NOT_TESTED:
    print(pin, end=" ")
print("\n")
