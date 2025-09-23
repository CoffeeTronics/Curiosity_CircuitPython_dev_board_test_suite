# boardtest_display_sprite_text.py
# SPDX-License-Identifier: MIT
#
# Display test that:
#  1) shows a moving sprite and asks the user to confirm it's moving (y/n),
#  2) then swaps to four text labels and asks for confirmation (y/n).
#
# Returns: ("PASS" | "FAIL (...)" | "SKIPPED (...)",
#           {"device":"ST7789","sprite_seen":bool,"text_seen":bool})

import time
import board
import displayio
import digitalio
import microcontroller
import supervisor
import usb_cdc
import terminalio
from adafruit_st7789 import ST7789

try:
    from fourwire import FourWire
except ImportError:
    from displayio import FourWire

_rx_buf = bytearray()

def _maybe_get_answer():
    if not supervisor.runtime.serial_connected:
        return None
    n = usb_cdc.console.in_waiting
    if not n:
        return None
    chunk = usb_cdc.console.read(n) or b""
    if not chunk:
        return None
    _rx_buf.extend(chunk)
    try:
        text = _rx_buf.decode("utf-8", "ignore")
    except Exception:
        text = "".join(chr(b) for b in _rx_buf if 32 <= b < 127)
    for ch in text:
        if ch in "\r\n\t ":
            continue
        c = ch.lower()
        _rx_buf[:] = b""
        if c in ("y", "n"):
            return c
        return None
    return None

def _setup_display():
    backlight = digitalio.DigitalInOut(microcontroller.pin.PA06)
    backlight.direction = digitalio.Direction.OUTPUT
    backlight.value = True

    displayio.release_displays()
    spi = board.LCD_SPI()
    bus = FourWire(spi, command=board.D13, chip_select=board.LCD_CS)
    display = ST7789(bus, rotation=270, width=240, height=135, rowstart=40, colstart=53)
    return display, backlight

def _make_sprite_group():
    # Tiny 16x16 2-color checker “sprite” built in RAM (no BMP load)
    bmp = displayio.Bitmap(16, 16, 2)
    pal = displayio.Palette(2)
    pal[0] = 0x003366
    pal[1] = 0x99CCFF
    for y in range(16):
        for x in range(16):
            bmp[x, y] = ((x ^ y) & 1)
    sprite = displayio.TileGrid(bmp, pixel_shader=pal)
    group = displayio.Group()
    group.append(sprite)
    return group, sprite

def _make_text_group():
    from adafruit_display_text import label
    t1 = label.Label(terminalio.FONT, text="Lorem ipsum dolor sit amet", color=0xFF00FF)
    t2 = label.Label(terminalio.FONT, text="consectetur adipiscing elit", color=0x0000FF)
    t3 = label.Label(terminalio.FONT, text="sed do eiusmod tempor incididunt ut", color=0xFF0000)
    t4 = label.Label(terminalio.FONT, text="labore et dolore magna aliqua", color=0x00FF00)
    t1.x, t1.y = 0, 20
    t2.x, t2.y = 0, 50
    t3.x, t3.y = 0, 80
    t4.x, t4.y = 0, 110
    parent = displayio.Group()
    parent.append(t1); parent.append(t2); parent.append(t3); parent.append(t4)
    return parent

def run_test(PINS, vx=1, vy=1, frame_delay=0.04, motion_prompt_delay_s=1.0,
             move_first=True, prompt_timeout_s=None):
    info = {"device": "ST7789", "sprite_seen": False, "text_seen": False}

    # Guard: missing pins => skip
    try:
        _ = board.LCD_SPI; _ = board.LCD_CS; _ = board.D13
    except Exception:
        return ("SKIPPED (display pins not present on this board)", info)

    display = None
    backlight = None
    spi_ref = None
    try:
        display, backlight = _setup_display()

        # Sprite phase
        group, sprite = _make_sprite_group()
        display.root_group = group
        WIDTH, HEIGHT = 240, 135
        sprite_width = 16
        sprite_height = 16
        # center
        group.x = (WIDTH - sprite_width) // 2
        group.y = (HEIGHT - sprite_height) // 2

        left = top = True
        right = bottom = False
        start = time.monotonic()
        prompted = False
        while True:
            if left:   group.x += vx
            if right:  group.x -= vx
            if top:    group.y += vy
            if bottom: group.y -= vy
            time.sleep(frame_delay)

            if group.x >= WIDTH - sprite_width:
                right, left = True, False
            if group.x <= 0:
                right, left = False, True
            if group.y >= HEIGHT - sprite_height:
                bottom, top = True, False
            if group.y <= 0:
                bottom, top = False, True

            if not prompted and (time.monotonic() - start) > motion_prompt_delay_s:
                print("\nDo you see the sprite moving around the screen? [y/n]")
                print("Type y or n, then press Enter.")
                prompted = True

            if prompted:
                ans = _maybe_get_answer()
                if ans == "y":
                    info["sprite_seen"] = True
                    break
                elif ans == "n":
                    return ("FAIL (sprite motion not visible)", info)

            if prompt_timeout_s is not None and (time.monotonic() - start) > prompt_timeout_s:
                return ("FAIL (timeout waiting for sprite confirmation)", info)

        # Text phase
        text_group = _make_text_group()
        display.root_group = text_group
        time.sleep(0.2)

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
        # Thorough teardown to prevent later hard faults
        try:
            if display is not None:
                display.root_group = None
        except Exception:
            pass
        try:
            displayio.release_displays()
        except Exception:
            pass
        # Backlight off then release
        try:
            if backlight is not None:
                try:
                    backlight.value = False
                except Exception:
                    pass
                backlight.deinit()
        except Exception:
            pass
        # Also free DC/CS quickly in case drivers left them claimed
        for name in ("D13", "LCD_CS"):
            try:
                dio = digitalio.DigitalInOut(getattr(board, name))
                dio.direction = digitalio.Direction.INPUT
                try:
                    dio.pull = None
                except Exception:
                    pass
                dio.deinit()
            except Exception:
                pass
        # Try to deinit the LCD SPI after release_displays (safe on most ports)
        try:
            spi_ref = board.LCD_SPI()
            try:
                spi_ref.deinit()
            except Exception:
                pass
        except Exception:
            pass
        import gc
        gc.collect()
        time.sleep(0.03)
