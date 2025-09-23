# boardtest_ble_uart.py
# BLE UART echo test via hardware UART to a BLE module.
# Pins: BLE_TX (MCU->module), BLE_RX (module->MCU), optional BLE_CLR (reset)
#
# RESULT = run_test(PINS, baudrate=9600, connect_timeout_s=60, user_timeout_s=120,
#                   do_reset=True, reset_active_low=True)
#
# Returns:
#   ( "PASSED" | "FAILED (...)" | "SKIPPED (...)",
#     ["BLE_TX","BLE_RX","BLE_CLR"?],
#     {"received": "<user text>", "connect_seen": True|False} )

import time
import board
import digitalio
import busio

def _get_pin(name):
    return getattr(board, name, None)

def _try_deinit(obj):
    try:
        obj.deinit()
    except Exception:
        pass

def _flush_rx(uart, max_ms=200):
    t0 = time.monotonic()
    while (time.monotonic() - t0) * 1000 < max_ms:
        n = uart.in_waiting
        if not n:
            break
        try:
            uart.read(n)
        except Exception:
            break
        time.sleep(0.005)

def _pulse_reset(clr_pin, active_low=True, ms=50, settle_ms=500):
    if not clr_pin:
        return
    dio = None
    try:
        dio = digitalio.DigitalInOut(clr_pin)
        dio.direction = digitalio.Direction.OUTPUT
        # Idle
        dio.value = True if active_low else False
        time.sleep(0.01)
        # Active pulse
        dio.value = False if active_low else True
        time.sleep(ms / 1000.0)
        # Back to idle and settle
        dio.value = True if active_low else False
        time.sleep(settle_ms / 1000.0)
    finally:
        if dio:
            _try_deinit(dio)

def _read_message(uart, timeout_s, idle_ms=250):
    """
    Non-blocking read until newline or short idle. Returns bytes (may be empty) or None on timeout.
    """
    deadline = time.monotonic() + timeout_s
    buf = bytearray()
    last_rx_ts = None

    while time.monotonic() < deadline:
        n = uart.in_waiting
        if n:
            chunk = uart.read(n)
            if chunk:
                buf += chunk
                last_rx_ts = time.monotonic()
                if b"\n" in buf or b"\r" in buf:
                    return bytes(buf).strip()
        else:
            if buf and last_rx_ts is not None:
                if (time.monotonic() - last_rx_ts) * 1000.0 > idle_ms:
                    return bytes(buf).strip()
        time.sleep(0.01)
    return None

def run_test(PINS,
             baudrate=9600,
             connect_timeout_s=60,
             user_timeout_s=120,
             echo_timeout_s=None,      # <— BACK-COMPAT alias
             do_reset=True,
             reset_active_low=True):
    """
    Wait for '%CONNECT', then prompt for a user string and echo it back.

    Back-compat:
      - If echo_timeout_s is provided, it will be used to override the default
        connect/user timeouts (unless you’ve explicitly set them).
    """
    tested = []
    info = {"received": "", "connect_seen": False}

    # --- Back-compat timeout mapping ---
    DEFAULT_CONNECT = 60
    DEFAULT_USER    = 120
    # If caller passed echo_timeout_s, use it where the defaults are still in effect
    if echo_timeout_s is not None:
        if connect_timeout_s == DEFAULT_CONNECT:
            connect_timeout_s = echo_timeout_s
        if user_timeout_s == DEFAULT_USER:
            user_timeout_s = echo_timeout_s

    # Ensure pins exist
    tx = getattr(board, "BLE_TX", None) if "BLE_TX" in PINS else None
    rx = getattr(board, "BLE_RX", None) if "BLE_RX" in PINS else None
    if tx is None or rx is None:
        return ("SKIPPED (BLE_TX/BLE_RX not available)", tested, info)

    tested.extend(["BLE_TX", "BLE_RX"])
    clr_pin = getattr(board, "BLE_CLR", None) if "BLE_CLR" in PINS else None
    if clr_pin is not None:
        tested.append("BLE_CLR")

    # helpers defined above: _pulse_reset, _flush_rx, _read_message, _try_deinit
    uart = None
    try:
        if do_reset and clr_pin is not None:
            _pulse_reset(clr_pin, active_low=reset_active_low)

        uart = busio.UART(tx=tx, rx=rx, baudrate=baudrate, timeout=0)
        _flush_rx(uart)

        #print("BLE UART Connect-and-Echo Test")
        print()
        print("1) Connect with your Serial Bluetooth Terminal app.")
        print('2) Send the literal string: %CONNECT')
        print("3) After '%CONNECT', send any text; I’ll print and echo it.\n")
        try:
            uart.write(b"READY: send %CONNECT\r\n")
        except Exception:
            pass

        # Phase 1: wait for %CONNECT
        msg = _read_message(uart, connect_timeout_s)
        text = msg.decode("utf-8", "replace") if msg else ""
        end = time.monotonic() + connect_timeout_s
        while text != "%CONNECT" and time.monotonic() < end:
            msg = _read_message(uart, max(0, end - time.monotonic()))
            text = msg.decode("utf-8", "replace") if msg else ""
            if not msg:
                break
        if text != "%CONNECT":
            return ("FAIL (did not receive %CONNECT)", tested, info)

        info["connect_seen"] = True
        print("Connected token received (%CONNECT). Now send a short line of text.\n")
        try:
            uart.write(b"OK CONNECTED\r\nSend text to echo:\r\n")
        except Exception:
            pass

        # Phase 2: wait for user text
        user_msg = _read_message(uart, user_timeout_s)
        if not user_msg:
            return ("FAIL (no user text received after %CONNECT)", tested, info)

        user_text = user_msg.decode("utf-8", "replace")
        info["received"] = user_text
        print(f"BLE received: {user_text}")

        try:
            uart.write(user_msg + b"\r\n")
        except Exception as e:
            return (f"FAIL (write error: {e})", tested, info)

        return ("PASS", tested, info)

    except Exception as e:
        return (f"FAIL ({e})", tested, info)

    finally:
        if uart:
            _try_deinit(uart)
