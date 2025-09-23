# SPDX-License-Identifier: MIT
"""
adafruit_boardtest.boardtest_analog_out
======================================
AnalogOut (DAC) test with immediate visible kick and quick fade start.
- Instantly sets a small DAC value so the LED lights up right after the banner.
- Uses larger steps and faster cadence for quicker visible fade.
- User can press Enter at any time to PASS (non-blocking).
- Always deinitializes the DAC.

Returns (PASS/FAIL/NA, [pin_used]).
"""

import sys
import time
import board
from analogio import AnalogOut

# Try to support non-blocking Enter on CircuitPython REPLs
try:
    import supervisor
except Exception:  # supervisor may not exist on some ports
    supervisor = None  # type: ignore

PASS = "PASS"
FAIL = "FAIL"
NA = "N/A"

# Tunables for quick visibility
VISIBLE_KICK = 4096   # ~6% of 16-bit full scale; adjust if your LED needs more/less
STEP = 64             # larger step so brightness changes are noticeable quickly
DELAY = 0.001         # faster cadence

def _find_analog_out(pins):
    """Return (pin_name, AnalogOut instance) for the first usable DAC pin; else (None, None)."""
    for name in pins:
        try:
            ao = AnalogOut(getattr(board, name))
            return name, ao
        except Exception:
            continue
    return None, None

def _enter_pressed():
    """Return True if user pressed Enter (non-blocking)."""
    if supervisor is None:
        return False
    try:
        pressed = False
        while supervisor.runtime.serial_bytes_available:
            ch = sys.stdin.read(1)
            if ch in ("\n", "\r"):
                pressed = True
        return pressed
    except Exception:
        return False

def run_test(pins, dac_pin):
    """
    Ramp a DAC pin with an immediate visible kick, allowing Enter to PASS.

    :param list pins: list of board pin names from dir(board)
    :param str dac_pin: preferred DAC-capable pin name (e.g., "DAC")
    :return: (result_str, [pin_used])
    """
    #print("@)}---^-----  ANALOG OUT TEST  -----^---{(@)")
    print()
    print('This test will ramp a DAC pin. Press Enter at any time to PASS.\n')

    ao = None
    pin_name = None

    # 1) Try requested DAC pin first
    if dac_pin is not None:
        try:
            ao = AnalogOut(getattr(board, dac_pin))
            pin_name = dac_pin
            print("Using requested DAC pin:", pin_name)
        except Exception as e:
            print("Requested DAC pin '{}' not usable: {}. Auto-detecting...".format(dac_pin, e))

    # 2) Fall back to auto-detect
    if ao is None:
        pin_name, ao = _find_analog_out(pins)

    if ao is None:
        print("No AnalogOut-capable pins found on this board.")
        return NA, []

    result = FAIL
    try:
        # Immediate visible kick so the LED starts glowing right away
        ao.value = VISIBLE_KICK
        time.sleep(0.02)

        interrupted = False

        # Two fade cycles (user can press Enter anytime to PASS)
        for _ in range(2):
            # Fade in
            for value in range(VISIBLE_KICK, 65536, STEP):
                ao.value = value
                if _enter_pressed():
                    interrupted = True
                    break
                time.sleep(DELAY)
            if interrupted:
                break

            # Fade out
            for value in range(65535, -1, -STEP):
                ao.value = value
                if _enter_pressed():
                    interrupted = True
                    break
                time.sleep(DELAY)
            if interrupted:
                break

        if interrupted:
            print("Enter detected. Marking test as PASS.")
            result = PASS
        else:
            # Fallback confirmation (blocking) if user didn't press Enter during fade
            try:
                input("Did you observe a clean ramp on the DAC pin? Press Enter for YES, Ctrl+C for NO.")
                result = PASS
            except KeyboardInterrupt:
                print("User indicated failure (Ctrl+C).")
                result = FAIL

    except KeyboardInterrupt:
        print("User indicated failure (Ctrl+C).")
        result = FAIL
    except Exception as e:
        print("AnalogOut error:", e)
        result = FAIL
    finally:
        try:
            ao.deinit()
        except Exception:
            pass
        print("AnalogOut deinitialized.")

    return result, [pin_name]
