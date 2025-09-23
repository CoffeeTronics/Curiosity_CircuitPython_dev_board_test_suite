# boardtest_ble_uart.py
# BLE UART echo test via hardware UART to a BLE module.
# Pins: BLE_TX (MCU->module), BLE_RX (module->MCU), optional BLE_CLR (reset)
#
# RESULT = run_test(
#   PINS,
#   baudrate=9600,
#   connect_timeout_s=60,
#   user_timeout_s=120,
#   echo_timeout_s=None,       # back-compat alias; mapped below
#   do_reset=True,
#   reset_active_low=True,
#   active_state_query=False,  # default OFF: avoid spamming AT+STATE? in data mode
#   state_query_period_s=1.0,
#   quiet_shutdown=True,       # NEW: hold module in reset before deinit
#   quiet_hold_ms=150          # NEW: reset hold time before flush/deinit
# )
#
# Returns a 3-tuple:
#   ( "PASS" | "FAIL (...)" | "SKIPPED (...)",
#     ["BLE_TX","BLE_RX",("BLE_CLR"?)] ,
#     {"received": "<user text (truncated)>", "connect_seen": bool, "connect_token": str} )

import time
import board
import digitalio
import busio

# Recognized connection tokens from popular modules (HM-10, BK, ESP-AT, etc.)
CONNECT_TOKENS = (
    b"OK+CONN",
    b"CONNECTED",
    b"CONNECT OK",
    b"LINK CONNECT",
    b"BT CONNECTED",
    b"BLE CONNECTED",
)

# ---- Memory/IO bounds to protect the heap and drivers ----
_MAX_STORE = 64     # what we keep in info["received"] for summaries
_MAX_LINE  = 128    # max bytes we accumulate for the user line
_CHUNK_MAX = 32     # clamp each uart.read() to this many bytes

def _get_pin(name):
    return getattr(board, name, None)

def _try_deinit(obj):
    try:
        obj.deinit()
    except Exception:
        pass

def _flush_rx(uart, max_ms=200):
    """Drain any pending RX to keep driver state clean and release buffers."""
    t0 = time.monotonic()
    while (time.monotonic() - t0) * 1000.0 < max_ms:
        n = uart.in_waiting
        if not n:
            break
        try:
            uart.read(min(n, _CHUNK_MAX))
        except Exception:
            break
        time.sleep(0.003)

def _pulse_reset(clr_pin, active_low=True, ms=50, settle_ms=500):
    if not clr_pin:
        return
    dio = None
    try:
        dio = digitalio.DigitalInOut(clr_pin)
        dio.direction = digitalio.Direction.OUTPUT
        # idle
        dio.value = True if active_low else False
        time.sleep(0.01)
        # active pulse
        dio.value = False if active_low else True
        time.sleep(ms / 1000.0)
        # back to idle & settle
        dio.value = True if active_low else False
        time.sleep(settle_ms / 1000.0)
    finally:
        if dio:
            _try_deinit(dio)

def _hold_reset(clr_pin, active_low=True):
    """Assert reset and KEEP it asserted (used for quiet shutdown)."""
    if not clr_pin:
        return None
    dio = digitalio.DigitalInOut(clr_pin)
    dio.direction = digitalio.Direction.OUTPUT
    # assert reset
    dio.value = False if active_low else True
    return dio  # caller must deinit/release later

def _release_reset(dio, active_low=True):
    """Release a held reset pin and deinit the DigitalInOut."""
    if not dio:
        return
    try:
        dio.value = True if active_low else False
    except Exception:
        pass
    _try_deinit(dio)

def _buffer_contains_any(buf, tokens):
    for t in tokens:
        if t in buf:
            return t
    return None

def _read_message_bounded(uart, timeout_s, idle_ms=250):
    """
    Read until newline, idle gap, or MAX_LINE bytes.
    Returns bytes (possibly truncated) or None on timeout.
    Bounded to avoid unbounded heap growth when the sender streams continuously.
    """
    deadline = time.monotonic() + timeout_s
    buf = bytearray()
    last_rx_ts = None

    while time.monotonic() < deadline:
        n = uart.in_waiting
        if n:
            # Clamp per read to avoid large allocations inside UART driver
            chunk = uart.read(min(n, _CHUNK_MAX))
            if chunk:
                buf += chunk
                # Early cap: if we hit MAX_LINE, return what we have
                if len(buf) >= _MAX_LINE:
                    return bytes(buf[:_MAX_LINE]).strip()
                last_rx_ts = time.monotonic()
                # Finished if line break arrived
                if b"\n" in buf or b"\r" in buf:
                    return bytes(buf).strip()
        else:
            # No new bytes
            if buf and last_rx_ts is not None:
                if (time.monotonic() - last_rx_ts) * 1000.0 > idle_ms:
                    return bytes(buf).strip()
        time.sleep(0.01)
    return None

def _wait_for_connection(uart, timeout_s, active_query, query_period_s):
    """
    Wait for a connection indication.
      - If active_query=True: send 'AT+STATE?' at most 10 times (rate-limited)
      - Treat any RX activity as proof of connection (transparent data mode)
    Returns (connected_bool, token_text or "").
    """
    deadline = time.monotonic() + timeout_s
    last_query = 0.0
    queries_sent = 0
    MAX_QUERIES = 10
    buf = bytearray()

    while time.monotonic() < deadline:
        now = time.monotonic()
        # Optional, capped active polling
        if active_query and queries_sent < MAX_QUERIES and (now - last_query) >= max(0.1, query_period_s):
            try:
                uart.write(b"AT+STATE?\r\n")
            except Exception:
                pass
            last_query = now
            queries_sent += 1

        # Read available bytes
        n = uart.in_waiting
        if n:
            chunk = uart.read(min(n, _CHUNK_MAX))
            if chunk:
                buf += chunk
                tok = _buffer_contains_any(buf, CONNECT_TOKENS)
                if tok:
                    return True, tok.decode("utf-8", "replace")
                # Transparent mode: any RX implies link is up
                return True, "RX ACTIVITY"
        time.sleep(0.02)

    return False, ""

def run_test(
    PINS,
    baudrate=9600,
    connect_timeout_s=60,
    user_timeout_s=120,
    echo_timeout_s=None,       # back-compat alias
    do_reset=True,
    reset_active_low=True,
    active_state_query=False,  # default OFF to avoid AT spam in data mode
    state_query_period_s=1.0,
    quiet_shutdown=True,       # NEW: assert reset before deinit to silence streamers
    quiet_hold_ms=150,         # NEW: how long to hold reset low/high before flush/deinit
):
    """
    Wait for a BLE link (token or any RX activity), then
    request a user string and echo it back.

    Returns:
      ("PASS"/"FAIL (...)"/"SKIPPED (...)", pins_used_list, info_dict)
    """
    tested = []
    info = {"received": "", "connect_seen": False, "connect_token": ""}

    # Back-compat: echo_timeout_s used to be a single timeout
    DEFAULT_CONNECT = 60
    DEFAULT_USER    = 120
    if echo_timeout_s is not None:
        if connect_timeout_s == DEFAULT_CONNECT:
            connect_timeout_s = echo_timeout_s
        if user_timeout_s == DEFAULT_USER:
            user_timeout_s = echo_timeout_s

    # Ensure pins exist
    if "BLE_TX" not in PINS or "BLE_RX" not in PINS:
        return ("SKIPPED (BLE_TX/BLE_RX not in PINS)", tested, info)

    tx = _get_pin("BLE_TX")
    rx = _get_pin("BLE_RX")
    if tx is None or rx is None:
        return ("SKIPPED (BLE_TX/BLE_RX not present on this board)", tested, info)

    tested.extend(["BLE_TX", "BLE_RX"])
    clr_pin = _get_pin("BLE_CLR") if "BLE_CLR" in PINS else None
    if clr_pin is not None:
        tested.append("BLE_CLR")

    uart = None
    held_reset = None

    try:
        # Optional power-on reset (short pulse) before starting
        if do_reset and clr_pin is not None:
            _pulse_reset(clr_pin, active_low=reset_active_low, ms=50, settle_ms=300)

        uart = busio.UART(tx=tx, rx=rx, baudrate=baudrate, timeout=0)
        _flush_rx(uart, max_ms=100)  # clear any stale bytes

        # Announce instructions
        try:
            uart.write(b"READY: waiting for BLE connection...\r\n")
        except Exception:
            pass

        # Phase 1: wait for connection (token or RX activity)
        connected, token = _wait_for_connection(
            uart,
            timeout_s=connect_timeout_s,
            active_query=active_state_query,
            query_period_s=state_query_period_s,
        )
        if not connected:
            return ("FAILED (no BLE connection detected within timeout)", tested, info)

        info["connect_seen"]  = True
        info["connect_token"] = token

        try:
            uart.write(b"OK CONNECTED\r\nSend text to echo:\r\n")
        except Exception:
            pass

        # Phase 2: read one line (bounded) and echo it back
        user_msg = _read_message_bounded(uart, user_timeout_s, idle_ms=250)
        if not user_msg:
            return ("FAILED (no user text received after connection)", tested, info)

        # Decode & store (bounded for summaries)
        user_text = user_msg.decode("utf-8", "replace")
        info["received"] = (user_text[:_MAX_STORE] + "…") if len(user_text) > _MAX_STORE else user_text

        # Echo back
        try:
            uart.write(user_msg + b"\r\n")
        except Exception as e:
            return (f"FAILED (write error: {e})", tested, info)

        # Drain any trailing RX then finish
        _flush_rx(uart, max_ms=50)
        return ("PASS", tested, info)

    except Exception as e:
        return (f"FAIL ({e})", tested, info)

    finally:
        # QUIET SHUTDOWN: if available, assert reset to silence the module first
        if quiet_shutdown and clr_pin is not None:
            try:
                held_reset = _hold_reset(clr_pin, active_low=reset_active_low)
                time.sleep(quiet_hold_ms / 1000.0)
            except Exception:
                held_reset = None

        if uart:
            _flush_rx(uart, max_ms=80)  # ensure RX is quiet before driver teardown
            _try_deinit(uart)

        # Release reset back to idle after UART is safely deinitialized
        if held_reset:
            _release_reset(held_reset, active_low=reset_active_low)
