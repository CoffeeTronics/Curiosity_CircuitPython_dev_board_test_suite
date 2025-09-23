# boardtest_dac_adc.py
# Uses board.DAC as AnalogOut and A0..A5 as AnalogIn inputs.
# Validates that each input tracks the DAC sweep (correlation + slope).
# Returns:
#   ( "PASS" | "FAIL (...)" | "SKIPPED (...)",
#     ["DAC","A0","A1", ...],           # <= NEW: plain pins list
#     {"output":"DAC","inputs":[...], "pass":[...], "fail":[...]} )

import time
import board
from analogio import AnalogOut, AnalogIn
import math

def _get(name):
    return getattr(board, name, None)

def _pearson_r(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x*x for x in xs); syy = sum(y*y for y in ys)
    sxy = sum(x*y for x, y in zip(xs, ys))
    num = n * sxy - sx * sy
    den = math.sqrt(max(1e-12, (n * sxx - sx * sx) * (n * syy - sy * sy)))
    return num / den

def _slope(xs, ys):
    n = len(xs)
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x*x for x in xs)
    sxy = sum(x*y for x, y in zip(xs, ys))
    den = (n * sxx - sx * sx)
    if abs(den) < 1e-12:
        return 0.0
    return (n * sxy - sx * sy) / den

def run_test(PINS, step=4096, dwell=0.002, repeats=1, verbose=False,
             r_min=0.98, slope_min=0.20, require_all_inputs=True):
    """
    Sweep DAC from 0..65535 while sampling A0..A5 (where present).
    Fail any input whose readings don't correlate with the DAC setpoints.

    Returns:
      status, pins_used_list, details_dict
    """
    details = {"output": None, "inputs": [], "pass": [], "fail": []}
    pins_used = []          # <= NEW
    ao = None
    adc_list = []           # [(name, AnalogIn)]
    fail_inputs = []        # names that fail or couldn't open
    pass_inputs = []

    # --- Required output pin ---
    if "DAC" not in PINS or _get("DAC") is None:
        return ("SKIPPED (DAC pin not available on this board)", pins_used, details)

    dac_pin = _get("DAC")
    details["output"] = "DAC"
    pins_used.append("DAC")

    # --- Candidate inputs A0..A5 present on this board ---
    candidate_inputs = [n for n in ("A0","A1","A2","A3","A4","A5")
                        if n in PINS and _get(n) is not None]
    if not candidate_inputs:
        return ("SKIPPED (no ADC inputs available)", pins_used, details)

    details["inputs"] = list(candidate_inputs)
    pins_used.extend(details["inputs"])

    try:
        # Create DAC
        ao = AnalogOut(dac_pin)
        ao.value = 0
        time.sleep(0.01)

        # Create each AnalogIn
        for name in candidate_inputs:
            try:
                adc_list.append((name, AnalogIn(_get(name))))
            except Exception:
                fail_inputs.append(name)  # couldn't open -> fail

        if not adc_list:
            return ("SKIPPED (failed to initialize all ADC inputs)", pins_used, details)

        # Up-sweep setpoints for validation
        step_i = max(1, int(step))
        setpoints = list(range(0, 65536, step_i))
        if setpoints[-1] != 65535:
            setpoints.append(65535)

        # Collect readings during up-sweep
        readings = {name: [] for name, _ in adc_list}
        for v in setpoints:
            ao.value = v
            time.sleep(dwell)
            for name, ai in adc_list:
                readings[name].append(ai.value)

        # Optional extra repeats (kept to match prior behavior; not needed for validation)
        for _ in range(max(0, repeats - 1)):
            for v in range(65535, -1, -step_i):
                ao.value = v
                time.sleep(dwell)
                _ = adc_list[0][1].value
            for v in setpoints:
                ao.value = v
                time.sleep(dwell)
                _ = adc_list[0][1].value

        # Per-input validation
        xs = [float(v) for v in setpoints]
        for name, _ in adc_list:
            ys = [float(y) for y in readings[name]]
            r = _pearson_r(xs, ys)
            m = _slope(xs, ys)
            if verbose:
                print(f"{name}: r={r:.3f}, slope={m:.3f}")
            if (r >= r_min) and (m >= slope_min):
                pass_inputs.append(name)
            else:
                fail_inputs.append(name)

        # Record details
        details["pass"] = list(dict.fromkeys(pass_inputs))
        details["fail"] = [n for n in details["inputs"] if n not in details["pass"]]

        # Overall status
        if require_all_inputs:
            if details["fail"]:
                return (f"FAIL (inputs not tracking: {', '.join(details['fail'])})",
                        pins_used, details)
            return ("PASS", pins_used, details)
        else:
            if details["pass"]:
                if details["fail"]:
                    return (f"PASS (but not tracking: {', '.join(details['fail'])})",
                            pins_used, details)
                return ("PASS", pins_used, details)
            else:
                return ("FAIL (no inputs tracked the DAC sweep)", pins_used, details)

    except Exception as e:
        return (f"FAIL ({e})", pins_used, details)

    finally:
        try:
            if ao:
                ao.value = 0
                ao.deinit()
        except Exception:
            pass
        for _, ai in adc_list:
            try:
                ai.deinit()
            except Exception:
                pass
