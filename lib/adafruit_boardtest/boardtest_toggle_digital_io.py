import time
import board
import digitalio

# --- Utility helpers ---------------------------------------------------------

def get_board_pin(name):
    """Return the board pin object (e.g. board.D0) if it exists, else None."""
    return getattr(board, name, None)

def make_dio(pin_obj, direction, pull=None):
    """Create a DigitalInOut, set direction/pull, return it."""
    dio = digitalio.DigitalInOut(pin_obj)
    dio.direction = direction
    if pull is not None and direction == digitalio.Direction.INPUT:
        dio.pull = pull
    return dio

def deinit_many(objs):
    for o in objs:
        try:
            o.deinit()
        except Exception:
            pass

def configure_groups(output_names, input_names, input_pull=None):
    """
    Create DigitalInOut objects for output and input groups.
    Returns (outputs, inputs) as lists of (name, dio).
    Skips pins that don't exist on the current board.
    """
    outputs = []
    inputs = []

    # Create outputs
    for name in output_names:
        pin = get_board_pin(name)
        if pin is None:
            print(f"Skipping {name}: not present on this board")
            continue
        try:
            dio = make_dio(pin, digitalio.Direction.OUTPUT)
            dio.value = False
            outputs.append((name, dio))
        except Exception as e:
            print(f"Skipping {name}: {e}")

    # Create inputs
    for name in input_names:
        pin = get_board_pin(name)
        if pin is None:
            print(f"Skipping {name}: not present on this board")
            continue
        try:
            dio = make_dio(pin, digitalio.Direction.INPUT, pull=input_pull)
            inputs.append((name, dio))
        except Exception as e:
            print(f"Skipping {name}: {e}")

    return outputs, inputs

def exercise_pairs(outputs, inputs, cycles=3, step_delay=0.1):
    """
    For each output pin, toggle HIGH then LOW while reading all inputs.
    """
    if not outputs or not inputs:
        print("Nothing to test in this phase (no outputs or no inputs).")
        return

    print("\n--- Exercising outputs --> reading inputs ---")
    print(f"Outputs: {[n for n, _ in outputs]}")
    print(f"Inputs : {[n for n, _ in inputs]}")
    for c in range(cycles):
        print(f"Cycle {c+1}/{cycles}")
        for out_name, out_dio in outputs:
            # Drive HIGH
            out_dio.value = True
            time.sleep(step_delay)
            readings = {in_name: in_dio.value for in_name, in_dio in inputs}
            print(f"  {out_name}=1  | inputs={readings}")

            # Drive LOW
            out_dio.value = False
            time.sleep(step_delay)
            readings = {in_name: in_dio.value for in_name, in_dio in inputs}
            print(f"  {out_name}=0  | inputs={readings}")
    print("--- Phase complete ---\n")

# --- Test 1: D0–D5 as outputs, D6–D11 as inputs ------------------------------

group_A_out = ["D0", "D1", "D2", "D3", "D4", "D5"]
group_B_in  = ["D6", "D7", "D8", "D9", "D10", "D11"]

outs, ins = configure_groups(group_A_out, group_B_in, input_pull=None)  # no pull to avoid fighting outputs
try:
    exercise_pairs(outs, ins, cycles=3, step_delay=0.1)
finally:
    deinit_many([d for _, d in outs] + [d for _, d in ins])

# --- Test 2: swap roles (D0–D5 inputs, D6–D11 outputs) -----------------------

group_A_in  = ["D0", "D1", "D2", "D3", "D4", "D5"]
group_B_out = ["D6", "D7", "D8", "D9", "D10", "D11"]

outs, ins = configure_groups(group_B_out, group_A_in, input_pull=None)
try:
    exercise_pairs(outs, ins, cycles=3, step_delay=0.1)
finally:
    deinit_many([d for _, d in outs] + [d for _, d in ins])

# --- Test 3: Pair test D0 <-> D13 (D0=input, D13=output) --------------------

print("\n--- D0 (INPUT)  <==  D13 (OUTPUT) ---")
outs, ins = configure_groups(["D13"], ["D0"], input_pull=None)
try:
    exercise_pairs(outs, ins, cycles=3, step_delay=0.1)
finally:
    deinit_many([d for _, d in outs] + [d for _, d in ins])

# --- Test 4: Pair test D0 <-> D13 (D0=output, D13=input) --------------------

print("\n--- D0 (OUTPUT)  ==>  D13 (INPUT) ---")
outs, ins = configure_groups(["D0"], ["D13"], input_pull=None)
try:
    exercise_pairs(outs, ins, cycles=3, step_delay=0.1)
finally:
    deinit_many([d for _, d in outs] + [d for _, d in ins])

print("All phases complete.")

