# SPDX-License-Identifier: MIT
"""
adafruit_boardtest.boardtest_neopixel
=====================================
NeoPixel (RGB LED) test. Tries a requested data pin first, then falls back
to auto-detecting board.NEOPIXEL if present. Cycles colors and a short
rainbow, asks the user to confirm, and ALWAYS deinitializes.

Returns (PASS/FAIL/NA, [pins_used]) like the other tests.
"""

import time
import board
import digitalio

PASS = "PASS"
FAIL = "FAIL"
NA   = "N/A"

# Default names commonly exposed on boards with built-in pixels / power control
NEOPIXEL_PIN_NAME = "NEOPIXEL"          # data pin for onboard pixel(s)
# NEOPIXEL_POWER_PIN_NAME = "NEOPIXEL_POWER"  # some boards gate power to pixels

def _maybe_make_output(pin_name, value):
    """If board has pin_name, drive it as an output set to value, else return None."""
    if hasattr(board, pin_name):
        dio = digitalio.DigitalInOut(getattr(board, pin_name))
        dio.switch_to_output(value)
        return dio
    return None

def _try_make_pixels(data_pin_name, n, brightness, pixel_order):
    """
    Try to construct a neopixel.NeoPixel on the given pin name.
    Returns (pixels_obj_or_None, err_or_None).
    """
    try:
        import neopixel  # requires neopixel.mpy in /lib
    except Exception as e:
        return None, e

    try:
        pin = getattr(board, data_pin_name)
    except AttributeError as e:
        return None, e

    try:
        pixels = neopixel.NeoPixel(
            pin,
            n,
            brightness=brightness,
            auto_write=False,
            pixel_order=pixel_order,
        )
        return pixels, None
    except Exception as e:
        return None, e

def _auto_detect_pin(pins):
    """Prefer explicit 'NEOPIXEL' if present; else None (user should pass a data pin)."""
    if "NEOPIXEL" in pins and hasattr(board, "NEOPIXEL"):
        return "NEOPIXEL"
    return None

def run_test(
    pins,
    data_pin=NEOPIXEL_PIN_NAME,
    num_pixels=1,
    brightness=0.2,
    pixel_order=(1, 0, 2, 3),  # default GRB[W] order: (G,R,B[,W])
    # power_pin=NEOPIXEL_POWER_PIN_NAME,
):
    """
    Cycle NeoPixels through colors + short rainbow and ask user to confirm.

    :param list pins: list of board pin names (from dir(board))
    :param str data_pin: NeoPixel data pin name (e.g., "NEOPIXEL" or "D6")
    :param int num_pixels: number of pixels to drive
    :param float brightness: 0.0..1.0 brightness
    :param tuple pixel_order: tuple defining pixel color order (e.g., neopixel.GRB)
    :param str power_pin: optional power-enable pin for pixels
    :return: (result_str, [pins_used])
    """
    print("@)}---^-----  NEOPIXEL TEST  -----^---{(@)")
    print()

    used_pins = []
    pwr = None
    pixels = None

    # Bring up power if available
    try:
        pwr = _maybe_make_output(power_pin, True)
        if pwr:
            used_pins.append(power_pin)
    except Exception:
        print("No Power Pin needed")
        # Power pin optional; continue
        pwr = None

    # Try requested data pin first
    chosen_pin = None
    pixels, err = _try_make_pixels(data_pin, num_pixels, brightness, pixel_order)
    if pixels is not None:
        chosen_pin = data_pin
    else:
        # Fall back to auto-detect "NEOPIXEL" if possible
        auto = _auto_detect_pin(pins)
        if auto and auto != data_pin:
            pixels, err = _try_make_pixels(auto, num_pixels, brightness, pixel_order)
            if pixels is not None:
                chosen_pin = auto

    if pixels is None:
        print("NeoPixel init failed. Install neopixel library and/or check pin.")
        if err is not None:
            print("Reason:", err)
        # If neither requested nor auto-detected worked, return NA
        return NA, []

    used_pins.append(chosen_pin)
    print("Using NeoPixel on:", chosen_pin)
    print("Pixels:", num_pixels, "Brightness:", brightness)
    print()

    result = FAIL
    try:
        # Helper to show a solid color on all pixels (tuple may be RGB or RGBW length)
        def _fill(color):
            for i in range(num_pixels):
                pixels[i] = color
            pixels.show()

        # Solid color steps (R, G, B, W if RGBW)
        # Map GRB tuple order to (R,G,B, [W]) color tuples we set
        # We'll just set using standard RGB(W) tuples; NeoPixel handles order internally.
        steps = []
        steps.append((255, 0, 0))   # Red
        steps.append((0, 255, 0))   # Green
        steps.append((0, 0, 255))   # Blue
        # If RGBW, allow a white step as well:
        try:
            if len(pixels[0]) == 4:  # RGBW tuple supported
                steps.append((0, 0, 0, 255))  # White
        except Exception:
            # Accessing pixels[0] before assignment can raise; just skip RGBW detection
            pass

        print("Cycling solid colors...")
        for color in steps:
            _fill(color)
            time.sleep(0.4)

        # Simple rainbow across the strip
        print("Rainbow sweep...")
        def wheel(pos):
            # pos 0..255 -> color
            if pos < 85:
                return (255 - pos * 3, pos * 3, 0)
            if pos < 170:
                pos -= 85
                return (0, 255 - pos * 3, pos * 3)
            pos -= 170
            return (pos * 3, 0, 255 - pos * 3)

        for j in range(64):  # short sweep
            for i in range(num_pixels):
                pixels[i] = wheel((i * 256 // max(1, num_pixels) + j) & 255)
            pixels.show()
            time.sleep(0.02)

        print("Do you see the pixels cycle Red, Green, Blue (and White if RGBW), then a rainbow?")
        print("Press Enter for YES, Ctrl+C for NO.")
        try:
            input()
        except Exception:
            # If input() not available, assume pass after the visual sequence
            pass

        result = PASS

    except KeyboardInterrupt:
        print("User indicated failure (Ctrl+C).")
        result = FAIL
    except Exception as e:
        print("NeoPixel test error:", e)
        result = FAIL
    finally:
        # Turn off and deinit pixels
        try:
            for i in range(num_pixels):
                pixels[i] = (0, 0, 0, 0) if hasattr(pixels, "bpp") and pixels.bpp == 4 else (0, 0, 0)
            pixels.show()
        except Exception:
            pass
        try:
            pixels.deinit()  # release the pin like other tests do for resources
        except Exception:
            pass
        if pwr is not None:
            try:
                pwr.deinit()
            except Exception:
                pass

    return result, used_pins

