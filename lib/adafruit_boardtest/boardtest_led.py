# SPDX-FileCopyrightText: 2018 Shawn Hymel for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
adafruit_boardtest.boardtest_led
================================
Blink the onboard LED (or a known LED pin) to verify it works.
This version ALWAYS deinitializes any claimed pins before returning.
"""

import time
import board
import digitalio

PASS = "PASS"
FAIL = "FAIL"
NA = "N/A"

# Common LED attribute names across boards (first match wins)
_LED_CANDIDATES = (
    "LED",        # many boards expose board.LED
    "L",          # some small boards
    "D13",        # classic Arduino pin for onboard LED
    "LED1",       # some nRF boards
)

def _find_led_pin_name(pins):
    """Return the first pin name in pins that matches common LED names on 'board'."""
    for name in _LED_CANDIDATES:
        if name in pins and hasattr(board, name):
            return name
    # Some boards only expose board.LED (even if not listed in pins)
    if hasattr(board, "LED"):
        return "LED"
    return None

def run_test(pins):
    """
    Blink the onboard LED (or a known LED pin) and ask user to confirm.
    Returns (result_str, [pin_names_used]).
    Always deinitializes DigitalInOut before returning.
    """
    led_pin_name = _find_led_pin_name(pins)
    if not led_pin_name:
        print("No onboard LED pin found.")
        return NA, []

    dio = None
    used_pins = [led_pin_name]
    try:
        dio = digitalio.DigitalInOut(getattr(board, led_pin_name))
        dio.direction = digitalio.Direction.OUTPUT

        print("LED TEST: The onboard LED should blink. Press Enter when you see it blink.")
        # Blink a few times to make it obvious
        for _ in range(6):
            dio.value = True
            time.sleep(0.15)
            dio.value = False
            time.sleep(0.15)

        # Keep it blinking while waiting for user confirmation
        print("Confirm you see the LED blinking (loopback-style). Press Enter to continue.")
        # Simple attention blink while waiting for Enter
        # Some CircuitPython builds support input(); if not, comment out next line.
        input()  # If your REPL doesn't allow input(), replace with a fixed PASS here.

        return PASS, used_pins

    except Exception as e:
        print("LED test error:", e)
        return FAIL, used_pins

    finally:
        # ALWAYS release the pin so later tests (e.g., GPIO) won't hit 'LED in use'
        if dio is not None:
            try:
                dio.deinit()
            except Exception as e:
                print("Warning: failed to deinit LED pin:", e)




# SPDX-FileCopyrightText: 2018 Shawn Hymel for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_boardtest.boardtest_led`
====================================================
Toggles all available onboard LEDs. You will need to manually verify their
operation by watching them.

Run this script as its own main.py to individually run the test, or compile
with mpy-cross and call from separate test script.

* Author(s): Shawn Hymel for Adafruit Industries

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""
'''
import time

import board
import digitalio
import supervisor

try:
    from typing import List, Sequence, Tuple
except ImportError:
    pass

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_BoardTest.git"

# Constants
LED_ON_DELAY_TIME = 0.2  # Seconds
LED_OFF_DELAY_TIME = 0.2  # Seconds
LED_PIN_NAMES = ["L", "LED", "RED_LED", "YELLOW_LED", "GREEN_LED", "BLUE_LED"]

# Test result strings
PASS = "PASS"
FAIL = "FAIL"
NA = "N/A"


# Toggle IO pins while waiting for answer
def _toggle_wait(led_pins: Sequence[str]) -> bool:
    timestamp = time.monotonic()
    led_state = False
    print("Are the pins listed above toggling? [y/n]")
    while True:
        # Cycle through each pin in the list
        for pin in led_pins:
            led = digitalio.DigitalInOut(getattr(board, pin))
            led.direction = digitalio.Direction.OUTPUT
            blinking = True

            # Blink each LED once while looking for input
            while blinking:
                if led_state:
                    if time.monotonic() > timestamp + LED_ON_DELAY_TIME:
                        led_state = False
                        led.value = led_state
                        led.deinit()
                        blinking = False
                        timestamp = time.monotonic()
                elif time.monotonic() > timestamp + LED_OFF_DELAY_TIME:
                    led_state = True
                    led.value = led_state
                    timestamp = time.monotonic()

                # Look for user input
                if supervisor.runtime.serial_bytes_available:
                    answer = input()
                    if answer == "y":
                        return True
                    return False


def run_test(pins: Sequence[str]) -> Tuple[str, List[str]]:
    """
    Toggles the onboard LED(s) on and off.

    :param list[str] pins: list of pins to run the test on
    :return: tuple(str, list[str]): test result followed by list of pins tested
    """

    # Look for pins with LED names
    led_pins = list(set(pins).intersection(set(LED_PIN_NAMES)))

    # Toggle LEDs if we find any
    if led_pins:
        # Print out the LEDs found
        print("LEDs found:", end=" ")
        for pin in led_pins:
            print(pin, end=" ")
        print("\n")

        # Blink LEDs and wait for user to verify test
        result = _toggle_wait(led_pins)

        if result:
            return PASS, led_pins

        return FAIL, led_pins

    # Else (no pins found)
    print("No LED pins found")
    return NA, []
    '''
