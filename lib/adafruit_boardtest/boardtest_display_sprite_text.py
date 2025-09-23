# boardtest_display_sprite_text.py
#
# Display test that:
#  1) shows a moving sprite and asks the user to confirm it's moving (y/n),
#  2) then swaps to four text labels and asks for confirmation (y/n).
#
# API (boardtest_* style):
#   status, info = run_test(PINS, vx=1, vy=1, frame_delay=0.04,
#                           motion_prompt_delay_s=1.0,
#                           move_first=True,
#                           prompt_timeout_s=None)
#
# Returns:
#   status: "PASS" | "FAIL (...)" | "SKIPPED (...)"
#   info:   {"device": "ST7789", "sprite_seen": bool, "text_seen": bool}

import time
import board
import displayio
import digitalio
import microcontroller
import supervisor
import usb_cdc
import adafruit_imageload
from adafruit_st7789 import ST7789
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label

# FourWire import (CP 9.x compatibility)
try:
    from fourwire import FourWire
except ImportError:
    from displayio import FourWire

# --- Non-blocking single-key y/n reader -------------------------------------
_rx_buf = bytearray()

def _maybe_get_answer():
    """
    Non-blocking: returns 'y', 'n', or None if no complete answer yet.
    Accepts uppercase/lowercase, does not require newline.
    """
    global _rx_buf
    if not supervisor.runtime.serial_connected:
        return None
    n = usb_cdc.console.in_waiting
    if not n:
        return None
    chunk = usb_cdc.console.read(n) or b""
    if not chunk:
        return None
    _rx_buf += chunk
    # Decode whatever we have so far
    try:
        text = _rx_buf.decode("utf-8", "ignore")
    except Exception:
        text = "".join(chr(b) for b in _rx_buf if 32 <= b < 127)
    # Look for the first non-whitespace character
    for ch in text:
        if ch in "\r\n\t ":
            continue
        c = ch.lower()
        # reset buffer on any first non-space char
        _rx_buf = bytearray()
        if c in ("y", "n"):
            return c
        return None
    return None
# -----------------------------------------------------------------------------

def _setup_display():
    """Initialize the ST7789 exactly as in your demo; return (display, backlight)."""
    # Backlight on PA06 (on your rig)
    backlight = digitalio.DigitalInOut(microcontroller.pin.PA06)
    backlight.direction = digitalio.Direction.OUTPUT
    backlight.value = True

    # Release & create bus/display
    displayio.release_displays()
    spi = board.LCD_SPI()
    tft_cs = board.LCD_CS
    tft_dc = board.D13
    bus = FourWire(spi, command=tft_dc, chip_select=tft_cs)
    display = ST7789(bus, rotation=270, width=240, height=135, rowstart=40, colstart=53)
    return display, backlight

def _make_sprite_group():
    """Load bitmap, create sprite and group centered on screen."""
    WIDTH, HEIGHT = 240, 135
    LOGO_W, LOGO_H = 32, 30

    # Load a 32x30 bitmap+palette (adjust path/name to your asset)
    bmp, pal = adafruit_imageload.load("Meatball_32x30_16color.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
    sprite = displayio.TileGrid(bmp, pixel_shader=pal, width=1, height=1)
    sprite.x = (WIDTH - LOGO_W) // 2
    sprite.y = (HEIGHT - LOGO_H) // 2

    group = displayio.Group()
    group.append(sprite)
    return group, LOGO_W, LOGO_H

def _make_text_group():
    """Create the four colored text labels and parent group."""
    font = bitmap_font.load_font("/Helvetica-Bold-16.bdf")
    t1 = label.Label(font, text="Lorem ipsum dolor sit amet", color=0xFF00FF)
    t2 = label.Label(font, text="consectetur adipiscing elit", color=0x0000FF)
    t3 = label.Label(font, text="sed do eiusmod tempor incididunt ut", color=0xFF0000)
    t4 = label.Label(font, text="labore et dolore magna aliqua", color=0x00FF00)

    t1.x, t1.y = 0, 20
    t2.x, t2.y = 0, 50
    t3.x, t3.y = 0, 80
    t4.x, t4.y = 0, 110

    parent = displayio.Group()
    parent.append(t1)
    g2 = displayio.Group(); g2.append(t2)
    g3 = displayio.Group(); g3.append(t3)
    g4 = displayio.Group(); g4.append(t4)
    parent.append(g2); parent.append(g3); parent.append(g4)
    return parent

def run_test(
    PINS,                      # kept for API consistency (unused here)
    vx=1, vy=1,                # pixels per frame
    frame_delay=0.04,          # seconds per frame during motion
    motion_prompt_delay_s=1.0, # wait a second so motion is visible
    move_first=True,           # keep True to match your flow
    prompt_timeout_s=None      # None = no timeout, else seconds per phase
):
    """
    Returns: ("PASS" | "FAIL (...)" | "SKIPPED (...)", info_dict)
    """
    info = {"device": "ST7789", "sprite_seen": False, "text_seen": False}

    # Hardware guardrails: bail out cleanly if the display pins are missing
    try:
        _ = board.LCD_SPI
        _ = board.LCD_CS
        _ = board.D4
    except Exception:
        return ("SKIPPED (display pins not present on this board)", info)

    display = None
    backlight = None
    try:
        # INIT
        display, backlight = _setup_display()

        # Build groups
        sprite_group, LOGO_W, LOGO_H = _make_sprite_group()
        text_group = _make_text_group()

        # Show sprite first
        display.root_group = sprite_group

        WIDTH, HEIGHT = 240, 135
        left = top = True
        right = bottom = False

        # --- Phase 1: motion & prompt ---
        start = time.monotonic()
        prompted = False
        while True:
            # Move
            if left:   sprite_group.x += vx
            if right:  sprite_group.x -= vx
            if top:    sprite_group.y += vy
            if bottom: sprite_group.y -= vy
            time.sleep(frame_delay)

            # Bounce
            if sprite_group.x >= WIDTH - LOGO_W:
                right, left = True, False
            if sprite_group.x <= 0:
                right, left = False, True
            if sprite_group.y >= HEIGHT - LOGO_H:
                bottom, top = True, False
            if sprite_group.y <= 0:
                bottom, top = False, True

            # Prompt after a short delay
            if not prompted and (time.monotonic() - start) > motion_prompt_delay_s:
                print("\nDo you see the sprite moving around the screen? [y/n]")
                print("Type y or n, then press Enter.")
                prompted = True

            # Read answer (non-blocking)
            if prompted:
                ans = _maybe_get_answer()
                if ans == "y":
                    info["sprite_seen"] = True
                    break
                elif ans == "n":
                    return ("FAILED (sprite motion not visible)", info)

            # Optional timeout
            if prompt_timeout_s is not None and (time.monotonic() - start) > prompt_timeout_s:
                return ("FAILED (timeout waiting for sprite confirmation)", info)

        # --- Phase 2: text & prompt ---
        display.root_group = text_group
        time.sleep(0.2)  # let the frame push

        start = time.monotonic()
        prompted = False
        while True:
            if not prompted:
                print("\nDo you see four lines of text on the screen? [y/n]")
                print("Type y or n, then press Enter.")
                prompted = True

            ans = _maybe_get_answer()
            if ans == "y":
                info["text_seen"] = True
                return ("PASS", info)
            elif ans == "n":
                return ("FAIL (text not visible)", info)

            if prompt_timeout_s is not None and (time.monotonic() - start) > prompt_timeout_s:
                return ("FAIL (timeout waiting for text confirmation)", info)

    except Exception as e:
        return (f"FAIL ({e})", info)

    finally:
        # ALWAYS release display + backlight pin (prevents hard faults in later tests)
        try:
            if display is not None:
                # Drop any groups so release_displays() can fully tear down the bus
                display.root_group = None
        except Exception:
            pass
        try:
            displayio.release_displays()
        except Exception:
            pass
        try:
            if backlight is not None:
                # Turn it off before releasing, just to be nice
                try:
                    backlight.value = False
                except Exception:
                    pass
                backlight.deinit()
        except Exception:
            pass
        time.sleep(0.02)
