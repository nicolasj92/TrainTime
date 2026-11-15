#!/usr/bin/env python3
"""
Ambient Colors mode: soft colour gradients that flow slowly across the panel.

Two gentle waves are mixed into a field and coloured with a palette. Every COLORS_MINUTES the
next palette fades in. Which palettes (and your own custom one) are chosen on the Modes page,
see color_palettes.py. Kept at moderate brightness: a full panel of colour draws a lot of power.
"""

import math
import os
import time

import numpy as np

from color_palettes import selected
from utils import Display, run

MINUTES = float(os.getenv("COLORS_MINUTES") or 3)
LEVEL = 0.75                                      # overall brightness



def lookup(colors, v):
    """v (0..1 arrays) -> RGB along a looping gradient through `colors`."""
    n = len(colors)
    pos = (v % 1.0) * n
    i = np.floor(pos).astype(int) % n
    k = (pos - np.floor(pos))[..., None]
    k = k * k * (3 - 2 * k)                       # smoothstep: no visible bands
    c = np.array(colors, dtype=np.float32)
    return c[i] * (1 - k) + c[(i + 1) % n] * k


class Colors:
    fps = 20

    def __init__(self, display: Display, clock=time.monotonic):
        self.d = display
        self.clock = clock
        self.start = clock()
        W, H = display.width, display.height
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.x, self.y = xx / 32, yy / 32           # same scale on both panel sizes
        self.palettes = [c for _, c in selected(os.getenv("COLORS_PALETTES"), os.getenv("COLORS_CUSTOM"))]

    def frame(self):
        t = self.clock() - self.start
        x, y = self.x, self.y
        # Two slow waves bending through each other, plus a drifting radial swell
        a = np.sin(x * 2.1 + t * 0.09 + 1.6 * np.sin(y * 1.7 + t * 0.05))
        b = np.sin(y * 2.6 - t * 0.07 + 1.3 * np.cos(x * 1.3 - t * 0.04))
        cx, cy = 1 + 0.8 * math.sin(t * 0.031), 0.5 + 0.4 * math.cos(t * 0.023)
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        c = np.sin(r * 3.2 - t * 0.12)
        v = (a + b + c) / 4 + 0.5 + t * 0.004       # slowly cycles through the palette too

        period = MINUTES * 60
        index, phase = divmod(t / period, 1)
        current = self.palettes[int(index) % len(self.palettes)]
        nxt = self.palettes[(int(index) + 1) % len(self.palettes)]
        img = lookup(current, v)
        fade = max(0.0, (phase - 0.85) / 0.15)      # last 15 % of each period: crossfade
        if fade > 0 and len(self.palettes) > 1:
            fade = fade * fade * (3 - 2 * fade)
            img = img * (1 - fade) + lookup(nxt, v) * fade
        self.d.image(np.clip(img * LEVEL, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    run(Colors)
