# SPDX-License-Identifier: MIT
"""
adafruit_boardtest.boardtest_pin_group_tester
=============================================
Safe digital pin pair connectivity test.

- Skips reserved/bus pins inside the library (SDA/SCL, NEOPIXEL, LED, CAN_*, QSPI_*, SD_*).
- Open-drain-safe: never drives HIGH. Float for "HIGH" phase; assert LOW only.
- Tests each pair in both directions for a number of cycles.
- Always deinitializes pins.

Returns (SUMMARY_STR, [PINS_TESTED])
"""

import time
import board
import digitalio

PASS = "PASS"
FAIL = "FAIL"
NA   = "N/A"

# Default pin pairs (adjust to your wiring/fixture as desired)
DEFAULT_PAIRS = [
    ("D11", "D10"),
    ("D9",  "D8"),
    ("D0",  "D1"),
    ("D2",  "D3"),
    ("D4",  "D5"),
    ("D6",  "D7"),
    # Add more safe GPIO↔GPIO pairs for your fixture as needed
]

# Pins that should not be exercised by push-pull tests
RESERVED = {
    # I2C
    "SDA", "SCL",
    # Onboard peripherals
    "NEOPIXEL", "LED",
    # CAN transceiver IOs
    "CAN_TX", "CAN_RX",
    # SD header SPI names seen in test rigs
    "SD_MOSI", "SD_MISO", "SD_SCK", "SD_CS",
    # External Flash (QuadSPI)
    "QSPI_CS", "QSPI_SCK", "QSPI_IO0", "QSPI_IO1", "QSPI_IO2", "QSPI_IO3",
    # Add any other board-specific reserved pins here if needed
}


def _has_board_pin(name):
    """Return True if 'board' exposes an attribute for this pin name."""
    try:
        getattr(board, name)
        return True
    except AttributeError:
        return False


def _make_input(pin_name, pull_up=True):
    """Create DigitalInOut configured as INPUT (optionally with PULL-UP)."""
    dio = digitalio.DigitalInOut(getattr(board, pin_name))
    dio.direction = digitalio.Direction.INPUT
    if pull_up:
        try:
            dio.pull = digitalio.Pull.UP
        except Exception:
            # Some ports/pins may not support pulls; ignore
            pass
    else:
        try:
            dio.pull = None
        except Exception:
            pass
    return dio


def _float_pin(dio):
    """Release a pin (high-impedance) by switching to input with no pull."""
    dio.switch_to_input()
    try:
        dio.pull = None
    except Exception:
        pass


def _drive_low(dio):
    """Assert LOW by switching to output low (open-drain style, never drives high)."""
    dio.switch_to_output(value=False)


def _exercise_one_direction(out_name, in_name, step_delay):
    """
    Exercise one direction (out_name -> in_name) with open-drain-safe behavior.
    Returns (ok_bool, float_read, low_read).
    """
    out_dio = None
    in_dio  = None
    ok = True
    float_read = None
    low_read = None

    try:
        # Input side with pull-up to create a defined high when line is floating
        in_dio  = _make_input(in_name, pull_up=True)
        # Output side starts released
        out_dio = digitalio.DigitalInOut(getattr(board, out_name))
        _float_pin(out_dio)

        # "Float" phase (acts like HIGH if the net has pull-ups)
        time.sleep(step_delay)
        try:
            float_read = in_dio.value
        except Exception:
            float_read = None

        # Assert LOW
        _drive_low(out_dio)
        time.sleep(step_delay)
        try:
            low_read = in_dio.value
        except Exception:
            low_read = None

        # We expect the input to read LOW when the output asserts LOW
        if low_read is not False:
            ok = False

        print(f"  {out_name}~FLOAT -> {in_name}={float_read} ; {out_name}=0 -> {in_name}={low_read}  [{'OK' if ok else 'FAIL'}]")

    except Exception as e:
        print(f"  Error testing {out_name}->{in_name}: {e}")
        ok = False
    finally:
        # Release pins
        try:
            if out_dio is not None:
                out_dio.deinit()
        except Exception:
            pass
        try:
            if in_dio is not None:
                in_dio.deinit()
        except Exception:
            pass

    return ok, float_read, low_read


def run_test(PINS, cycles=3, step_delay=0.1, pairs=None):
    """
    Run the safe pin-pair connectivity test.

    :param list PINS: list of pin names from dir(board)
    :param int cycles: number of A->B + B->A cycles per pair
    :param float step_delay: seconds to wait between state changes
    :param list pairs: optional list of (pinA, pinB) tuples; defaults to DEFAULT_PAIRS
    :return: (summary_str, [pins_tested])
    """
    PAIRS = list(pairs) if pairs is not None else list(DEFAULT_PAIRS)

    # Filter to pairs that are present on this board and not reserved
    valid_pairs = []
    for a, b in PAIRS:
        if a in RESERVED or b in RESERVED:
            print(f"Skipping pair {a}<->{b}: reserved/bus pin")
            continue
        if (a in PINS and b in PINS and _has_board_pin(a) and _has_board_pin(b)):
            valid_pairs.append((a, b))
        else:
            print(f"Skipping pair {a}<->{b}: not available on this board")

    if not valid_pairs:
        return "Pin Pair Test: SKIPPED (no valid pairs)", []

    overall_ok = True
    tested_pins = set()

    print("Pin Pair List (safe/open-drain):", valid_pairs)
    print(f"Cycles: {cycles}, Step Delay: {step_delay}s")
    print()

    for (a, b) in valid_pairs:
        print(f"Testing pair {a} <-> {b}")
        for _ in range(int(cycles)):
            ok1, _, _ = _exercise_one_direction(a, b, step_delay)
            ok2, _, _ = _exercise_one_direction(b, a, step_delay)
            if not (ok1 and ok2):
                overall_ok = False
        tested_pins.add(a)
        tested_pins.add(b)
        print()

    summary = "Pin Pair Test: PASS" if overall_ok else "Pin Pair Test: FAIL"
    return summary, sorted(tested_pins)
