#!/usr/bin/env python3
"""
Power Flow mode: live solar / grid / house power from Home Assistant.

64 wide: clock, then sun -> house -> grid side by side with their values. Glowing particles
         run along the connections in the direction the power flows, faster the more flows.
         The bar at the bottom shows how much of the house's power comes from the sun.
32x32:   the same three as rows, connected by a vertical flow line.

Colours: solar amber, house white, grid green when feeding in and orange when buying.
"""

import math
import os
import threading
import time

import numpy as np
import requests

from utils import Display, run

HA_URL = os.getenv('HA_URL', 'http://homeassistant.local:8123').rstrip('/')
HA_TOKEN = os.getenv('HA_TOKEN')
HA_SOLAR_ENTITY = os.getenv('HA_SOLAR_ENTITY', 'sensor.balkonkraftwerk_power')
HA_GRID_ENTITY = os.getenv('HA_GRID_ENTITY', 'sensor.main_power')
POLL_SECONDS = 5


class PowerSource:
    """Polls Home Assistant in a background thread. grid < 0 means feeding into the grid."""

    def __init__(self):
        self.solar = 0
        self.grid = 0
        self.error = None if HA_TOKEN else "No HA token"

    @property
    def home(self):
        return round(self.grid + self.solar)

    def _read(self, entity_id):
        response = requests.get(
            f'{HA_URL}/api/states/{entity_id}',
            headers={'Authorization': f'Bearer {HA_TOKEN}'},
            timeout=5,
        )
        response.raise_for_status()
        try:
            return round(float(response.json()['state']))
        except ValueError:  # 'unavailable' / 'unknown'
            return 0

    def poll_forever(self):
        while True:
            try:
                self.solar = self._read(HA_SOLAR_ENTITY)
                self.grid = self._read(HA_GRID_ENTITY)
                self.error = None
            except Exception as e:
                print(f"Home Assistant error: {e}", flush=True)
                self.error = "HA error"
            time.sleep(POLL_SECONDS)

    def start(self):
        if HA_TOKEN:
            threading.Thread(target=self.poll_forever, daemon=True).start()
        return self


# --- Look -------------------------------------------------------------------------

SOLAR = (255, 176, 40)
HOUSE = (235, 235, 245)
EXPORT = (60, 220, 110)
IMPORT = (255, 110, 40)
TEXT_DIM = (150, 150, 165)

# 9x9 pixel art. Letters pick colours (see _icon_colors), "." is empty.
ICONS = {
    "sun": [
        "....r....",
        ".r.....r.",
        "...ccc...",
        "..ccccc..",
        "r.ccccc.r",
        "..ccccc..",
        "...ccc...",
        ".r.....r.",
        "....r....",
    ],
    "house": [
        "....R....",
        "...RRR...",
        "..RRRRR..",
        ".RRRRRRR.",
        "RRRRRRRRR",
        ".WWWWWWW.",
        ".WwwWWDW.",
        ".WwwWWDW.",
        ".WWWWWDW.",
    ],
    "grid": [            # lattice pylon with two cross-arms
        "P...P...P",
        "PPPPPPPPP",
        "...PPP...",
        "...P.P...",
        ".PPPPPPP.",
        "..PP.PP..",
        "..P.P.P..",
        ".PP...PP.",
        ".P.....P.",
    ],
}


def fmt(watts):
    watts = abs(round(watts))
    if watts >= 10000:
        return f"{watts / 1000:.0f}kW"
    if watts >= 1000:
        return f"{watts / 1000:.1f}kW"
    return f"{watts}W"


def speed(watts):
    """Pixels per second for a flow of `watts`: 6 at 50 W up to 18 at 3 kW, on a log scale."""
    return 6 + 12 * max(0.0, min(1.0, math.log10(max(watts, 50) / 50) / math.log10(60)))


class Flow:
    """Particles moving along a path of pixels, like light pulses in a cable."""

    SPACING = 5

    def __init__(self, path):
        self.path = path
        self.offset = 0.0

    def draw(self, img, color, watts, forward, dt, track=True):
        n = len(self.path)
        if track:   # faint line so the connection is visible even when nothing flows
            for x, y in self.path:
                img[y, x] = np.maximum(img[y, x], np.array(color) * 0.12)
        if watts < 5:
            return
        self.offset = (self.offset + speed(watts) * dt) % self.SPACING
        start = self.offset
        while start < n:
            for back, level in ((0, 1.0), (1, 0.45), (2, 0.18)):      # head and fading tail
                pos = start - back
                i0 = math.floor(pos)
                frac = pos - i0
                for i, w in ((i0, 1 - frac), (i0 + 1, frac)):        # split between pixels: smooth
                    if 0 <= i < n:
                        x, y = self.path[i if forward else n - 1 - i]
                        img[y, x] = np.minimum(255, img[y, x] + np.array(color) * level * w)
            start += self.SPACING


class PowerFlow:
    fps = 30

    def __init__(self, display: Display, source=None):
        self.d = display
        self.source = source or PowerSource().start()
        self.t = 0.0
        W, H = display.width, display.height
        self.W, self.H = W, H
        if display.wide:
            y = 13
            self.pos = {"sun": (4, 9), "house": (28, 9), "grid": (52, 9)}
            self.solar_flow = Flow([(x, y) for x in range(14, 27)])
            self.grid_flow = Flow([(x, y) for x in range(38, 51)])
        else:
            self.pos = {"sun": (0, 0), "house": (0, 11), "grid": (0, 22)}
            self.solar_flow = Flow([(10, y) for y in range(4, 16)])
            self.grid_flow = Flow([(10, y) for y in range(15, 27)])

    def frame(self):
        s = self.source
        if s.error and not (s.solar or s.grid):
            self.d.error(s.error)
            return
        dt = 1 / self.fps
        self.t += dt
        solar, grid = max(0, s.solar), s.grid
        home = max(0, solar + grid)
        exporting = grid < 0
        grid_color = EXPORT if exporting else IMPORT

        img = np.zeros((self.H, self.W, 3), dtype=np.float32)
        self._icon(img, "sun", solar)
        self._icon(img, "house", home)
        self._icon(img, "grid", abs(grid), grid_color)
        self.solar_flow.draw(img, SOLAR, solar, True, dt)
        self.grid_flow.draw(img, grid_color, abs(grid), exporting, dt)
        if not self.d.wide:            # stubs from the icons to the vertical line
            for y in (4, 15, 26):
                img[y, 9] = np.maximum(img[y, 9], (40, 40, 48))
        elif home > 0:                 # solar share of the house's consumption
            share = min(solar, home) / home
            split = round(share * self.W)
            img[31, :split] = np.array(SOLAR) * 0.55
            img[31, split:] = np.array(IMPORT) * 0.35
        self.d.image(np.clip(img, 0, 255).astype(np.uint8))

        d = self.d
        values = [("sun", solar, SOLAR), ("house", home, HOUSE), ("grid", grid, grid_color)]
        if d.wide:
            d.text(d.font_large, (self.W - d.text_width(d.font_large, d.time_str()) + 1) // 2, 6, TEXT_DIM, d.time_str())
            for name, watts, color in values:
                text = fmt(watts)
                cx = self.pos[name][0] + 4
                x = max(0, min(self.W - d.text_width(d.font_small, text), cx - d.text_width(d.font_small, text) // 2 + 1))
                d.text(d.font_small, x, 27, color, text)
        else:
            for (name, watts, color), baseline in zip(values, (7, 18, 29)):
                text = fmt(watts)
                d.text(d.font_small, self.W - d.text_width(d.font_small, text), baseline, color, text)

    def _icon(self, img, name, watts, accent=None):
        x0, y0 = self.pos[name]
        active = watts >= 5
        glow = 0.55 + 0.45 * math.sin(self.t * 2.2)              # slow pulse of the sun's rays
        colors = {
            "sun": {"c": SOLAR if active else (70, 70, 90),
                    "r": tuple(c * (0.35 + 0.65 * glow) for c in SOLAR) if active else (30, 30, 40)},
            "house": {"R": (110, 120, 150), "W": (200, 200, 210), "w": (255, 200, 90) if active else (60, 60, 70),
                      "D": (70, 60, 55)},
            "grid": {"P": tuple(0.4 * c + 0.6 * g for c, g in zip(accent or (150, 160, 175), (150, 160, 175)))
                     if active else (90, 95, 110)},
        }[name]
        for dy, row in enumerate(ICONS[name]):
            for dx, ch in enumerate(row):
                if ch in colors and 0 <= y0 + dy < self.H and 0 <= x0 + dx < self.W:
                    img[y0 + dy, x0 + dx] = colors[ch]


if __name__ == "__main__":
    run(PowerFlow)
