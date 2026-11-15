#!/usr/bin/env python3
"""
Fireplace mode: a calm fire filling the whole panel, for cosy evenings.

The flames are drawn, not simulated: a few teardrop-shaped flame tongues sit on the logs.
Each one slowly grows, shrinks and sways (smooth, unhurried motion), and a soft turbulence
pattern drifting upwards breaks up their edges. Heat is coloured from deep red over orange
to a yellow-white core. Embers glow on the logs, sparks rise now and then, and a faint warm
glow lights the dark behind the flames.

FIRE_BEDTIME (e.g. 23:00, empty = never): from then on the fire burns down over half an hour
to glowing embers, and comes back at 6:00.
"""

import math
import os
import random
import time
from datetime import datetime

import numpy as np
from PIL import Image

from utils import Display, run

BEDTIME = os.getenv("FIRE_BEDTIME") or ""


def wobble(t, seed):
    """Smooth noise in -1..1: a few slow sines with unrelated frequencies."""
    return (math.sin(t * 1.13 + seed) + 0.6 * math.sin(t * 1.97 + seed * 2.3)
            + 0.35 * math.sin(t * 3.41 + seed * 0.7)) / 1.95


def palette():
    """Heat 0..1 -> colour: black, ember red, orange, golden, yellow-white core."""
    stops = [(0.0, (0, 0, 0)), (0.12, (40, 3, 0)), (0.3, (150, 22, 0)), (0.5, (235, 75, 5)),
             (0.7, (255, 140, 20)), (0.86, (255, 195, 60)), (1.0, (255, 235, 150))]
    table = np.zeros((256, 3), dtype=np.float32)
    for i in range(256):
        h = i / 255
        for (h0, c0), (h1, c1) in zip(stops, stops[1:]):
            if h <= h1:
                k = (h - h0) / (h1 - h0)
                table[i] = [a + (b - a) * k for a, b in zip(c0, c1)]
                break
    return table


def turbulence(width, height, seed=11):
    """Soft noise that wraps around vertically (it scrolls upwards forever)."""
    rng = np.random.default_rng(seed)
    total = np.zeros((height, width), dtype=np.float32)
    for cell, weight in ((6, 1.0), (3, 0.5)):
        gw, gh = max(2, width // cell + 2), max(2, height // cell)
        grid = rng.random((gh, gw)).astype(np.float32)
        big = Image.fromarray(np.tile(grid, (3, 1))).resize((width + 2 * cell, height * 3), Image.BICUBIC)
        total += weight * np.asarray(big)[height:2 * height, cell:cell + width]
    total -= total.min()
    return total / total.max()


class Fire:
    fps = 15                                   # motion is slow and smooth; spares the Pi 3

    def __init__(self, display: Display, now=None, clock=time.monotonic):
        self.d = display
        self.now = now or datetime.now
        self.clock = clock
        self.start = clock()
        W, H = display.width, display.height
        self.W, self.H = W, H
        wide = display.wide
        self.palette = palette()
        self.side = 0                                   # full screen: no fireplace surround
        self.top = 0
        self.hearth = H
        self.logs_y = H - 3
        self.base = self.logs_y - 1                      # flames stand on the logs
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.xx, self.yy = xx, yy
        self.noise = turbulence(W, H * 2)
        rnd = random.Random(3)
        # Flame tongues: centre x, half width at the base, height; the middle ones tallest
        inner = W - 2 * self.side
        count = 10 if wide else 5
        self.tongues = []
        for i in range(count):                          # overlapping, irregular tongues
            frac = (i + 0.5) / count
            middle = 1 - abs(frac - 0.5) * 1.7
            self.tongues.append({
                "x": inner * (0.04 + 0.92 * frac) + rnd.uniform(-1.5, 1.5),
                "w": (4.2 if wide else 3.0) * rnd.uniform(0.75, 1.2),
                "h": (self.base - self.top) * (0.65 + 0.45 * middle) * rnd.uniform(0.85, 1.1),
                "seed": rnd.uniform(0, 100)})
        self.bed = (1, W - 2)                           # glowing bed of flame along the logs
        self.background = self._build_background()
        self.logs = self._build_logs()
        self.embers = [(x, y, rnd.uniform(0, 100)) for x, y, _ in self.logs[::4]]
        self.inside = np.zeros((H, W), dtype=bool)
        self.inside[self.top:self.hearth, self.side:W - self.side] = True
        self.sparks = []
        self.rng = random.Random()

    # --- static parts ---

    def _build_background(self):
        """Dark, with a faint warm haze rising from the bottom."""
        depth = (np.arange(self.H, dtype=np.float32) / (self.H - 1)) ** 2
        img = np.zeros((self.H, self.W, 3), dtype=np.float32)
        img[:] = (depth[:, None, None] * np.array((14, 4, 1), dtype=np.float32))
        return img

    def _build_logs(self):
        pixels = []
        x0, x1 = 1, self.W - 2
        mid = (x0 + x1) // 2
        for x in range(x0, x1 + 1):
            for dy, color in ((0, (84, 48, 24)), (1, (62, 34, 17)), (2, (40, 21, 11))):
                pixels.append((x, self.logs_y + dy, color))
        for x in (x0, x1):                              # cut ends of the log, lighter wood
            pixels.append((x, self.logs_y + 1, (120, 80, 45)))
        half = 16 if self.d.wide else 8
        for x in range(mid - half, mid + half + 1):    # second log across the first
            pixels.append((x, self.logs_y - 1, (92, 54, 28)))
        return pixels

    # --- animation ---

    def _strength(self):
        """1 = full fire, down to 0.2 = embers (only with FIRE_BEDTIME)."""
        if not BEDTIME:
            return 1.0
        try:
            hh, mm = map(int, BEDTIME.split(":"))
        except ValueError:
            return 1.0
        now = self.now()
        minutes = now.hour * 60 + now.minute
        bed = hh * 60 + mm
        since = (minutes - bed) % (24 * 60)
        if since < 30:
            return 1.0 - 0.8 * since / 30
        if since < (6 * 60 - bed) % (24 * 60):        # between bedtime and 6:00
            return 0.2
        return 1.0

    def _heat(self, t, strength):
        yy = self.yy
        # turbulence scrolling upwards bends the flames sideways and breaks up their edges
        rows = (np.arange(self.H) + int(t * 8)) % self.noise.shape[0]
        rows2 = (np.arange(self.H) + int(t * 5) + self.H // 2) % self.noise.shape[0]
        n = self.noise[rows]
        xx = self.xx + (self.noise[rows2][:, ::-1] - 0.5) * 3.0 * np.clip((self.base - yy) / 10, 0, 1.5)
        heat = np.zeros((self.H, self.W), dtype=np.float32)
        x0, x1 = self.bed
        bed = np.clip(1 - (self.base - yy) / 4.5, 0, 1) * (yy <= self.base)
        bed *= np.clip(np.minimum(self.xx - x0, x1 - self.xx) / 3 + 0.3, 0, 1)
        heat = np.maximum(heat, 0.75 * bed * strength ** 0.5)
        for f in self.tongues:
            s = f["seed"]
            height = f["h"] * strength * (0.8 + 0.2 * wobble(t * 0.9, s))
            if height < 1:
                continue
            rel = (self.base - yy) / height             # 0 at the base, 1 at the tip
            up = np.clip(rel, 0, 1)
            sway = 2.2 * wobble(t * 0.45, s + 7) * up ** 1.6
            bulge = 0.7 + 0.3 * np.clip(up * 5, 0, 1)    # widest a little above the base
            half = f["w"] * (0.9 + 0.1 * wobble(t * 1.3, s + 3)) * (1 - up) ** 0.8 * bulge
            dist = np.abs(xx - f["x"] - sway) / np.maximum(half, 0.01)
            body = np.clip(1 - dist, 0, 1) ** 0.6 * (1 - up) ** 0.5
            body *= rel > -0.12                         # nothing below the logs
            heat = np.maximum(heat, body)
        heat = heat * (0.45 + 0.9 * n)
        # soften: a light blur turns pixel spikes into rounded licks of flame
        heat[:, 1:-1] = 0.25 * heat[:, :-2] + 0.5 * heat[:, 1:-1] + 0.25 * heat[:, 2:]
        heat[1:-1] = 0.2 * heat[:-2] + 0.6 * heat[1:-1] + 0.2 * heat[2:]
        heat = np.clip(heat * 1.15, 0, 1)
        heat[self.base + 1:] = 0
        return np.clip(heat, 0, 1)

    def frame(self):
        t = self.clock() - self.start
        strength = self._strength()
        heat = self._heat(t, strength)
        img = self.background.copy()
        fire = self.palette[(heat * 255).astype(np.uint8)]
        img[self.inside] = np.maximum(img[self.inside], fire[self.inside])

        # firelight on the logs, gently flickering
        glow = (0.7 + 0.15 * wobble(t * 2.1, 1) + 0.15 * wobble(t * 3.3, 2)) * strength

        for x, y, color in self.logs:
            img[y, x] = np.array(color) * (0.8 + 0.5 * glow)
        for x, y, s in self.embers:                     # embers pulse slowly, not randomly
            level = max(0.0, wobble(t * 0.8, s)) * (0.4 + 0.6 * strength)
            if level > 0.15:
                img[y, x] = np.maximum(img[y, x], np.array((255, 80, 15)) * level)
        self._sparks(img, strength)
        self.d.image(np.clip(img, 0, 255).astype(np.uint8))

    def _sparks(self, img, strength):
        if self.rng.random() < 0.025 * strength:
            f = self.rng.choice(self.tongues)
            self.sparks.append([f["x"] + self.rng.uniform(-1.5, 1.5), float(self.base - 3),
                                self.rng.uniform(-0.06, 0.06), self.rng.uniform(0.2, 0.35), 1.0])
        alive = []
        for s in self.sparks:
            s[0] += s[2] + 0.05 * math.sin(s[1] * 0.8)
            s[1] -= s[3]
            s[4] -= 0.02
            x, y = round(s[0]), round(s[1])
            if s[4] > 0 and self.top <= y and self.side <= x < self.W - self.side:
                img[y, x] = np.maximum(img[y, x], np.array((255, 200, 90)) * s[4])
                alive.append(s)
        self.sparks = alive


if __name__ == "__main__":
    run(Fire)
