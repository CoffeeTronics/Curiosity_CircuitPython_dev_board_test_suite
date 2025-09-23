# SPDX-License-Identifier: MIT
"""
adafruit_boardtest.boardtest_move_board
======================================
Simple user-prompt test that asks the operator to move the dev board to a
specified section of the test rig, then waits for Enter to continue.

Returns (PASS/FAIL/NA, [pins_used]) to match the other tests.
"""

import sys
import time

PASS = "DONE"
FAIL = "NOT DONE"
NA   = "N/A"

# Try to import supervisor for non-blocking serial reads; OK if unavailable
try:
    import supervisor
except Exception:  # pragma: no cover
    supervisor = None  # type: ignore

def _wait_for_enter():
    """
    Wait for Enter using input(); fall back to non-blocking serial if needed.
    Raises KeyboardInterrupt if the user Ctrl+C's.
    """
    # Preferred: blocking input() (works on most CircuitPython REPLs)
    try:
        input()
        return
    except KeyboardInterrupt:
        raise
    except Exception:
        # Fallback: non-blocking read via supervisor (if available)
        if supervisor is not None:
            try:
                while True:
                    # Drain until we see '\r' or '\n'
                    while supervisor.runtime.serial_bytes_available:
                        ch = sys.stdin.read(1)
                        if ch in ("\n", "\r"):
                            return
                    time.sleep(0.05)
            except KeyboardInterrupt:
                raise
        else:
            # Last resort: give the operator a short pause and continue
            # (Some environments don't support input() or supervisor)
            time.sleep(2.0)
            return

def run_test(pins, location_label="LOWER section"):
    """
    Ask the user to move the dev board to a given location and press Enter.

    :param list pins: list of board pin names (unused, for API consistency)
    :param str location_label: text describing where to move the board
    :return: (result_str, [pins_used])
    """
    print("@)}---^-----  SETUP STEP  -----^---{(@)")
    print()
    print("Please move the dev board to the {} on the test rig.".format(location_label))
    print("Press Enter to continue.")
    try:
        _wait_for_enter()
        return PASS, []   # no pins claimed
    except KeyboardInterrupt:
        print("Setup interrupted by user (Ctrl+C).")
        return FAIL, []

