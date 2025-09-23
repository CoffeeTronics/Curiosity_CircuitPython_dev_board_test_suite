# /lib/adafruit_boardtest/boardtest_can.py
# SPDX-License-Identifier: MIT
"""
adafruit_boardtest.boardtest_can
================================
CAN test using canio. Sends a few frames and verifies they are received.
If the first RX times out in normal mode, the test automatically restarts
in controller loopback and retries (useful for single-node setups).

Returns (PASS/FAIL/NA, [pins_used]).
"""

import struct
import time
import board
import canio
import digitalio

# Result strings
PASS = "PASS"
FAIL = "FAIL"
NA   = "N/A"

# Defaults (adjust to your board as needed)
CAN_TX_PIN_NAME = "CAN_TX"
CAN_RX_PIN_NAME = "CAN_RX"
CAN_STANDBY_PIN_NAME = "CAN_STANDBY"  # ATA6561: STBY = 0 → Normal, 1 → Standby
CAN_BAUD = 250_000
MSG_ID = 0x408
NUM_FRAMES = 3
RECV_TIMEOUT_S = 0.9
AUTO_RESTART = True

def _maybe_make_output(pin_name, initial_value):
    """If board exposes pin_name, return DigitalInOut set as output to initial_value; else None."""
    if hasattr(board, pin_name):
        dio = digitalio.DigitalInOut(getattr(board, pin_name))
        dio.switch_to_output(initial_value)
        return dio
    return None

def _drain(listener):
    """Drain any pending frames."""
    try:
        while listener.receive() is not None:
            pass
    except Exception:
        pass

def _open_can(rx_name, tx_name, baudrate, loopback):
    """Create a canio.CAN with desired params."""
    return canio.CAN(
        rx=getattr(board, rx_name),
        tx=getattr(board, tx_name),
        baudrate=baudrate,
        auto_restart=AUTO_RESTART,
        loopback=loopback,
    )

def run_test(
    pins,
    tx_pin=CAN_TX_PIN_NAME,
    rx_pin=CAN_RX_PIN_NAME,
    baudrate=CAN_BAUD,
    message_id=MSG_ID,
    standby_pin=CAN_STANDBY_PIN_NAME,
    loopback=False,           # start mode; if first RX times out and loopback==False, we auto-fallback to loopback
    num_frames=NUM_FRAMES,
    recv_timeout=RECV_TIMEOUT_S,
):
    """
    Send num_frames CAN messages and verify they are received (normal or loopback).
    Auto-fallback: if the first receive times out in normal mode, re-init in loopback and retry.

    :param list pins: list of pin names from dir(board)
    :param str tx_pin: board attribute name for CAN TX
    :param str rx_pin: board attribute name for CAN RX
    :param int baudrate: CAN bit rate
    :param int message_id: standard 11-bit CAN ID to use
    :param str standby_pin: optional ATA6561 STBY pin (LOW for Normal mode)
    :param bool loopback: start in controller loopback (True) or normal (False)
    :param int num_frames: number of frames to send/verify
    :param float recv_timeout: listener timeout (seconds)
    :return: (result_str, [pins_used])
    """
    #print("@)}---^-----  CAN TEST  -----^---{(@)")
    print()

    # Verify pins exist
    if not (hasattr(board, tx_pin) and hasattr(board, rx_pin)):
        print("No CAN TX/RX pins found on this board.")
        return NA, []

    # If starting in normal mode, let user confirm wiring/termination
    if not loopback:
        print("Ensure ATA6561 transceiver is connected, STBY is low (Normal), and bus is terminated (120Ω at each end).")
        print("Press Enter to start the CAN test (or continue if input() not available).")
        try:
            input()
        except Exception:
            pass

    used_pins = [tx_pin, rx_pin]
    can = None
    listener = None
    standby_dio = None

    try:
        # ATA6561: STBY low → Normal mode. Drive low if the pin exists.
        standby_dio = _maybe_make_output(standby_pin, False)
        if standby_dio:
            used_pins.append(standby_pin)

        # Open CAN in requested mode
        can = _open_can(rx_pin, tx_pin, baudrate, loopback)
        listener = can.listen(matches=[canio.Match(message_id)], timeout=recv_timeout)
        _drain(listener)

        print("CAN bus state:", can.state)
        print("Transmitting and verifying {} frame(s) @ {} bit/s ...".format(num_frames, baudrate))
        print()

        fallback_done = False

        def _send_and_expect(count):
            """Send one frame and expect exact echo (id+payload). Returns (rx_msg_or_None, payload)."""
            now_ms = (time.monotonic_ns() // 1_000_000) & 0xFFFFFFFF
            payload = struct.pack("<II", count, now_ms)
            msg = canio.Message(id=message_id, data=payload)
            print("TX: id=0x{:03X} count={} now_ms={}".format(message_id, count, now_ms))
            can.send(msg)
            rx = listener.receive()
            return rx, payload

        # For each frame:
        count = 0
        while count < num_frames:
            rx, payload = _send_and_expect(count)

            if rx is None:
                # First receive failed and we are not in loopback yet? Auto-fallback.
                if not loopback and not fallback_done and count == 0:
                    print("RX timeout on first frame; retrying in controller loopback mode...")
                    # Re-init CAN in loopback
                    try:
                        listener = None
                        can.deinit()
                    except Exception:
                        pass
                    can = _open_can(rx_pin, tx_pin, baudrate, True)
                    listener = can.listen(matches=[canio.Match(message_id)], timeout=recv_timeout)
                    _drain(listener)
                    loopback = True
                    fallback_done = True
                    # Retry the same frame number in loopback
                    rx, payload = _send_and_expect(count)

                    if rx is None:
                        print("RX timeout even in loopback.")
                        return FAIL, used_pins
                else:
                    print("RX timeout waiting for frame {}".format(count))
                    return FAIL, used_pins

            # Validate the received frame
            if rx.id != message_id:
                print("RX unexpected ID: 0x{:03X} (expected 0x{:03X})".format(rx.id, message_id))
                return FAIL, used_pins

            if rx.data != payload:
                print("RX payload mismatch (len={}): {}".format(len(rx.data), list(rx.data)))
                return FAIL, used_pins

            # Optional decode print for visibility
            r_count, r_now_ms = struct.unpack("<II", rx.data)
            print("RX: id=0x{:03X} count={} now_ms={} (OK)".format(rx.id, r_count, r_now_ms))

            count += 1

        print()
        print("All {} frame(s) were received correctly.".format(num_frames))
        return PASS, used_pins

    except Exception as e:
        print("CAN test error:", e)
        return FAIL, used_pins

    finally:
        # Clean up in reverse order
        try:
            if listener is not None:
                listener = None
        except Exception:
            pass
        try:
            if can is not None:
                can.deinit()
        except Exception:
            pass
        try:
            if standby_dio is not None:
                standby_dio.deinit()
        except Exception:
            pass

