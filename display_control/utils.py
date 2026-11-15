#!/usr/bin/env python3
"""
Shared LED matrix code: panel configuration, the Display class (drawing helpers that
work for any panel size), pixel icons, and the main loop every display mode uses.

A display mode is a class with `fps`, `__init__(self, display)` and `frame(self)`, where
frame() draws one frame. See christmas_display.py for an example.
"""

import os
import socket
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

# All settings live in display_control/.env (see .env.example)
load_dotenv(Path(__file__).resolve().parent / '.env')

# Fonts are loaded after rgbmatrix drops root privileges to user 'daemon', which can't
# read /home/pi, so install.sh copies fonts/ here.
font_dir = os.getenv('FONT_DIR', '/usr/share/fonts/bdf')

# Panel presets. Both use 32x32 panel modules (64x32 = two chained), connected to the
# HAT's second output (parallel=2), so the visible area starts at row 32 of the canvas.
PANEL_PRESETS = {
    '64x32': dict(rows=32, cols=32, chain=2, parallel=2, y_offset=32),
    '32x32': dict(rows=32, cols=32, chain=1, parallel=2, y_offset=32),
}

color_blue = [48, 118, 179]
color_black = [0, 0, 0]
color_yellow = [255, 255, 0]
color_red = [255, 0, 0]


def default_gpio_slowdown():
    """Pick a GPIO slowdown that suits the Pi model (faster CPU -> higher value)."""
    try:
        model = Path('/proc/device-tree/model').read_text()
    except OSError:
        return 4
    if 'Pi 5' in model or 'Pi 4' in model:
        return 4
    if 'Pi 3' in model:
        return 2
    return 1


def panel_config():
    """Panel geometry from LED_PANEL, with optional per-value overrides from .env."""
    name = os.getenv('LED_PANEL') or '64x32'
    if name not in PANEL_PRESETS:
        raise ValueError(f"LED_PANEL={name!r}, expected one of {', '.join(PANEL_PRESETS)}")
    cfg = dict(PANEL_PRESETS[name])
    for key in cfg:
        value = os.getenv(f'LED_{key.upper()}')
        if value:
            cfg[key] = int(value)
    return cfg


# --- Icons (8x8 unless stated) -----------------------------------------------------

class Icon(object):
    def __init__(self, display, pos_x, pos_y):
        self.display = display
        self.width = 8
        self.height = 8
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.content = np.zeros((self.width, self.height, 3))
        self.define_icon()

    def define_icon(self):
        raise NotImplementedError()

    def draw(self):
        for x in range(self.width):
            for y in range(self.height):
                self.display.set_pixel(x + self.pos_x, y + self.pos_y, *self.content[x, y])


class IconBus(Icon):
    def define_icon(self):
        self.content[1:7, 1:7] = color_blue

        self.content[2:6, 2:4] = color_black
        self.content[2:6, 6] = color_black

        self.content[2, 4] = color_yellow
        self.content[5, 4] = color_yellow


class IconTram(Icon):
    def define_icon(self):
        self.content[1:7, 1:7] = color_blue
        self.content[2:6, 2:4] = color_black
        self.content[1, 1] = color_black
        self.content[6, 1] = color_black
        self.content[1, 5] = color_black
        self.content[6, 5] = color_black
        self.content[2:6, 6] = color_black
        self.content[3:5, 5] = color_black

        self.content[2, 4] = color_yellow
        self.content[5, 4] = color_yellow


class IconTrain(Icon):
    """S-Bahn / regional train: green body, window band, wheels."""
    def define_icon(self):
        green = [0, 140, 70]
        self.content[1:7, 1:6] = green
        self.content[2:6, 2:4] = color_black
        self.content[1, 1] = color_black
        self.content[6, 1] = color_black
        self.content[2, 4] = color_yellow
        self.content[5, 4] = color_yellow
        self.content[2, 6] = [120, 120, 120]
        self.content[5, 6] = [120, 120, 120]


class IconError(Icon):
    def define_icon(self):
        self.content[1:7, 1:7] = color_red


class IconSun(Icon):
    def define_icon(self):
        circle_center = 3.5
        radius = 2.0
        for x in range(1, 7):
            for y in range(1, 7):
                if (x - circle_center) ** 2 + (y - circle_center) ** 2 <= radius ** 2:
                    self.content[x, y] = [255, 165, 0]
        ray_positions = [(3, 0), (3, 7), (0, 3), (7, 3), (1, 1), (6, 1), (1, 6), (6, 6)]
        for x, y in ray_positions:
            self.content[x, y] = [255, 165, 0]


class IconHouse(Icon):
    def define_icon(self):
        self.content[3, 1] = [100, 149, 237]
        self.content[2, 2] = self.content[4, 2] = [100, 149, 237]
        self.content[1, 3] = self.content[5, 3] = [100, 149, 237]
        for x in range(2, 5):
            for y in range(4, 7):
                self.content[x, y] = [100, 149, 237]


class IconGrid(Icon):
    def define_icon(self):
        c = [100, 149, 237]
        for x, y in [(2, 6), (3, 6), (4, 6), (2, 5), (3, 4), (4, 5),
                     (1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (3, 2)]:
            self.content[x, y] = c


class IconWifi(Icon):
    def define_icon(self):
        c = [110, 170, 255]
        for x in range(1, 7):
            self.content[x, 1] = c
        self.content[0, 2] = self.content[7, 2] = c
        for x in range(2, 6):
            self.content[x, 3] = c
        self.content[1, 4] = self.content[6, 4] = c
        self.content[3, 5] = self.content[4, 5] = c
        self.content[3, 7] = self.content[4, 7] = c


# --- Display -----------------------------------------------------------------------

class Display:
    """
    The visible area of the LED panel. Modes draw in visible coordinates
    (0..width-1, 0..height-1); the panel's y_offset is added here.
    """

    def __init__(self):
        cfg = panel_config()
        options = RGBMatrixOptions()
        options.rows = cfg['rows']
        options.cols = cfg['cols']
        options.chain_length = cfg['chain']
        options.parallel = cfg['parallel']
        options.gpio_slowdown = int(os.getenv('LED_GPIO_SLOWDOWN') or default_gpio_slowdown())
        self.matrix = RGBMatrix(options=options)
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()

        self.y_offset = cfg['y_offset']
        self.width = cfg['cols'] * cfg['chain']
        self.height = cfg['rows'] * cfg['parallel'] - self.y_offset
        print(f"Panel {self.width}x{self.height} (rows={cfg['rows']} cols={cfg['cols']} "
              f"chain={cfg['chain']} parallel={cfg['parallel']} y_offset={self.y_offset}), "
              f"gpio_slowdown={options.gpio_slowdown}", flush=True)

        self.font_small = graphics.Font()
        self.font_small.LoadFont(os.path.join(font_dir, "4x6.bdf"))
        self.font_large = graphics.Font()
        self.font_large.LoadFont(os.path.join(font_dir, "5x7.bdf"))
        self.white = graphics.Color(255, 255, 255)

    @property
    def wide(self):
        """True for 64-pixel-wide panels, False for 32x32."""
        return self.width >= 64

    def clear(self):
        self.offscreen_canvas.Clear()

    def swap(self):
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)

    def set_pixel(self, x, y, r, g, b):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.offscreen_canvas.SetPixel(x, y + self.y_offset, r, g, b)

    def image(self, pixels):
        """Draw a whole frame at once from a (height, width, 3) uint8 numpy array (fast)."""
        from PIL import Image
        self.offscreen_canvas.SetImage(Image.fromarray(pixels, 'RGB'), 0, self.y_offset)

    def text(self, font, x, y, color, text):
        """Draw text with its baseline at y. Returns the width drawn."""
        if isinstance(color, tuple):
            color = graphics.Color(*color)
        return graphics.DrawText(self.offscreen_canvas, font, x, y + self.y_offset, color, text)

    @staticmethod
    def text_width(font, text):
        return sum(max(font.CharacterWidth(ord(c)), 0) for c in text)

    @staticmethod
    def time_str():
        return datetime.now().strftime("%H:%M")

    def clock(self, y=6):
        """Draw HH:MM centred at the top. Returns (x, width)."""
        time_str = self.time_str()
        width = self.text_width(self.font_large, time_str)
        x = (self.width - width + 1) // 2
        self.text(self.font_large, x, y, self.white, time_str)
        return x, width

    def error(self, message):
        """Clock, red square and a short message. Used by modes when something fails."""
        self.clear()
        self.clock()
        IconError(self, (self.width - 8) // 2, 10).draw()
        font = self.font_large if self.wide else self.font_small
        self.text(font, 0, 24, self.white, message)


# --- Wi-Fi setup screen ------------------------------------------------------------

HOTSPOT_STATE = Path('/run/pidisplay/hotspot.json')  # written by deploy/bin/wifi-fallback


class WifiSetupScreen:
    """Shown instead of the current mode while the setup hotspot is up."""

    def __init__(self, display, ssid, password, ip):
        self.d = display
        self.lines = [ssid, f"pw {password}", ip]
        self.ticker = f"Join {ssid}  pw {password}  open {ip}   "
        self.scroll = 0

    def frame(self):
        d = self.d
        d.clear()
        IconWifi(d, 0, 0).draw()
        d.text(d.font_small, 10, 6, (110, 170, 255), "WiFi setup" if d.wide else "WiFi")
        if d.wide:
            for i, line in enumerate(self.lines):
                d.text(d.font_small, 0, 14 + i * 7, d.white, line)
        else:
            width = d.text_width(d.font_large, self.ticker)
            x = -(self.scroll % width)
            while x < d.width:
                x += d.text(d.font_large, x, 22, d.white, self.ticker)
            self.scroll += 1


def read_hotspot_state():
    try:
        import json
        return json.loads(HOTSPOT_STATE.read_text())
    except (OSError, ValueError):
        return None


# --- Running a mode ----------------------------------------------------------------

def get_lock():
    """Abstract-namespace socket lock so only one mode drives the panel at a time."""
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind('\0traintime_display')
        return lock_socket
    except socket.error:
        return None


def run(mode_class):
    """Main loop shared by all modes: create the display, then draw frames forever."""
    lock = get_lock()
    if lock is None:
        print("Another display mode is already running (sudo systemctl stop traintime)")
        return
    display = Display()
    mode = mode_class(display)
    print(f"Starting {mode_class.__name__}...", flush=True)
    setup_screen, next_check = None, 0
    try:
        while True:
            started = time.monotonic()
            if started >= next_check:  # is the Wi-Fi setup hotspot up?
                state = read_hotspot_state()
                if state and setup_screen is None:
                    setup_screen = WifiSetupScreen(display, state['ssid'], state['password'], state['ip'])
                elif not state:
                    setup_screen = None
                next_check = started + 2
            current = setup_screen or mode
            frame_time = 1.0 / (15 if setup_screen else mode.fps)
            try:
                current.frame()
            except Exception as e:  # keep the panel alive and show what went wrong
                print(f"Error drawing frame: {e!r}", flush=True)
                display.error("Error")
                time.sleep(5)
            display.swap()
            time.sleep(max(0.0, frame_time - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()
        display.swap()
        lock.close()
