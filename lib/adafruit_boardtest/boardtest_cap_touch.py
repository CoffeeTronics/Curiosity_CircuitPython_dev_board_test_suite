# SPDX-License-Identifier: MIT
"""
adafruit_boardtest.boardtest_cap_touch
======================================
Capacitive-touch test. Tries a requested touch-capable pin first, then
auto-detects a usable pin. Lights the LED on touch, asks for a touch and
release within timeouts, and ALWAYS deinitializes.

Returns (PASS/FAIL/NA, [pins_used]) like the other tests.
"""

import time
import board
import digitalio

PASS = "PASS"
FAIL = "FAIL"
NA   = "N/A"

# Default pin names mirror your Cap_Touch_test.py (A5 and LED)
CAP_TOUCH_PIN_NAME = "CAP1"
LED_PIN_NAME       = "LED"

def _maybe_led(pin_name):
    """Return a DigitalInOut LED set as output (LOW), or None if not present."""
    try:
        if hasattr(board, pin_name):
            dio = digitalio.DigitalInOut(getattr(board, pin_name))
            dio.direction = digitalio.Direction.OUTPUT
            dio.value = False
            return dio
    except Exception:
        pass
    return None

def _try_make_touch(pin_name):
    """Try to construct a touchio.TouchIn on the given board pin name. Return (obj, err)."""
    try:
        import touchio  # built-in on boards that support capacitive touch
    except Exception as e:
        return None, e

    try:
        tp = touchio.TouchIn(getattr(board, pin_name))
        return tp, None
    except Exception as e:
        return None, e

def _auto_find_touch_pin(pins):
    """
    Scan provided 'pins' for a usable TouchIn pin.
    Returns (pin_name, touch_obj) or (None, None).
    """
    for name in pins:
        tp, _ = _try_make_touch(name)
        if tp is not None:
            return name, tp
    return None, None

def run_test(
    pins,
    touch_pin=CAP_TOUCH_PIN_NAME,
    led_pin=LED_PIN_NAME,
    touch_timeout_s=8.0,
    release_timeout_s=8.0,
    poll_interval_s=0.05,
):
    """
    Ask the user to touch then release the pad. LED (if present) mirrors touch state.

    :param list pins: list of board pin names (from dir(board))
    :param str touch_pin: preferred capacitive touch pad (e.g., "A5")
    :param str led_pin: LED pin name to indicate touch (optional)
    :param float touch_timeout_s: seconds to detect initial touch
    :param float release_timeout_s: seconds to detect release
    :param float poll_interval_s: polling interval in seconds
    :return: (result_str, [pins_used])
    """
    #print("@)}---^-----  CAPACITIVE TOUCH TEST  -----^---{(@)")
    print()

    used_pins = []
    led = _maybe_led(led_pin)
    if led:
        used_pins.append(led_pin)

    tp = None
    pin_name = None

    # Try the requested pin first
    if touch_pin is not None:
        tp, err = _try_make_touch(touch_pin)
        if tp is not None:
            pin_name = touch_pin
        else:
            print("Requested touch pin '{}' not usable: {}".format(touch_pin, err))

    # Fall back to auto-detection
    if tp is None:
        pin_name, tp = _auto_find_touch_pin(pins)

    if tp is None:
        print("No capacitive-touch capable pin found on this board.")
        # Clean LED and exit
        if led:
            try: led.deinit()
            except Exception: pass
        return NA, []

    used_pins.append(pin_name)
    print("Using capacitive touch on:", pin_name)
    print("Touch the pad; LED (if present) will light on touch.")

    result = FAIL
    try:
        # Phase 1: wait for touch
        print("Waiting for TOUCH ({} s timeout)...".format(touch_timeout_s))
        t0 = time.monotonic()
        while True:
            val = tp.value
            if led: led.value = bool(val)
            if val:
                print("Touched!")
                break
            if time.monotonic() - t0 > touch_timeout_s:
                print("Timeout waiting for touch.")
                return FAIL, used_pins
            time.sleep(poll_interval_s)

        # Phase 2: wait for release
        print("Now RELEASE the pad ({} s timeout)...".format(release_timeout_s))
        t0 = time.monotonic()
        while True:
            val = tp.value
            if led: led.value = bool(val)
            if not val:
                print("Released!")
                result = PASS
                break
            if time.monotonic() - t0 > release_timeout_s:
                print("Timeout waiting for release.")
                result = FAIL
                break
            time.sleep(poll_interval_s)

    except KeyboardInterrupt:
        print("User indicated failure (Ctrl+C).")
        result = FAIL
    except Exception as e:
        print("Capacitive touch error:", e)
        result = FAIL
    finally:
        # Turn off LED and deinit resources
        if led:
            try:
                led.value = False
                led.deinit()
            except Exception:
                pass
        if tp:
            try:
                tp.deinit()
            except Exception:
                pass

    return result, used_pins

