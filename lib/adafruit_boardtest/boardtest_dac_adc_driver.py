# boardtest_dac_adc.py
# Sweep a DAC pin while sampling ADC on A0, boardtest_* API:
#   run_test(PINS, step=..., dwell=..., repeats=...)
# Returns: ("PASSED" | "FAILED (...)" | "SKIPPED (...)",
#           ["<tested pin names>"])

import time
import board
from analogio import AnalogOut, AnalogIn

def _get(name):
    return getattr(board, name, None)

def _find_dac_pin(PINS, exclude_name="A0"):
    """
    Find a DAC-capable analog pin whose *name* is in PINS and is not exclude_name.
    We probe by attempting AnalogOut() construction.
    """
    # Prefer A1 first (common DAC), then other A* names in PINS
    ordered = []
    if "A1" in PINS: ordered.append("A1")
    # add remaining Ax that are in PINS (dedup)
    ordered += [n for n in PINS if n.startswith("A") and n not in ("A0", "A1")]
    for name in ordered:
        if name == exclude_name:
            continue
        pin = _get(name)
        if not pin:
            continue
        try:
            test = AnalogOut(pin)
            test.deinit()
            return name, pin
        except Exception:
            pass
    return None, None

def _counts_to_volts(adc_obj, counts):
    return (counts / 65535.0) * adc_obj.reference_voltage

def run_test(PINS, step=4096, dwell=0.002, repeats=1, verbose=False):
    """
    Drives a DAC-capable pin from 0..65535 while reading ADC on A0.
    Hardware expectation: wire the chosen DAC pin to A0 externally.

    Returns ("PASSED", tested_names) on success,
            ("SKIPPED (<reason>)", tested_names) if not runnable,
            ("FAILED (<reason>)", tested_names) on unexpected error.
    """
    tested = []

    # Ensure A0 exists and is in the PINS list
    if "A0" not in PINS or _get("A0") is None:
        return ("SKIPPED (A0 not available on this board)", tested)

    ai = None
    ao = None
    try:
        # ADC on A0
        ai = AnalogIn(_get("A0"))
        tested.append("A0")

        # Find a DAC that isn't A0 (so we can measure it on A0)
        dac_name, dac_pin = _find_dac_pin(PINS, exclude_name="A0")
        if not dac_pin:
            # No DAC distinct from A0 available; skip gracefully
            return ("SKIPPED (no DAC distinct from A0 found)", tested)

        ao = AnalogOut(dac_pin)
        tested.append(dac_name)

        # Quick settle
        ao.value = 0
        time.sleep(0.01)

        if verbose:
            print(f"DAC on {dac_name}; ADC on A0 (ref ~{ai.reference_voltage:.2f} V).")
            print("Jumper DAC->A0 for measurement.")

        # Sweep up & down
        for _ in range(repeats):
            # ramp up
            v = 0
            while v <= 65535:
                ao.value = v
                time.sleep(dwell)
                _ = ai.value  # take a reading (keep console quiet by default)
                v += step

            # ramp down
            v = 65535
            while v >= 0:
                ao.value = v
                time.sleep(dwell)
                _ = ai.value
                v -= step

        # Success
        return ("PASSED", tested)

    except Exception as e:
        return (f"FAILED ({e})", tested)

    finally:
        # Clean up
        try:
            if ao:
                ao.value = 0
                ao.deinit()
        except Exception:
            pass
        try:
            if ai:
                ai.deinit()
        except Exception:
            pass
