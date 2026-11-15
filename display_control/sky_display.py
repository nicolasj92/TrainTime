#!/usr/bin/env python3
"""
Sky clock: the real sky over SKY_LAT/SKY_LON, with the clock on top.

- sky colours follow the sun's altitude (night, dawn/dusk pink and orange, day blue)
- the sun and moon move across the sky to their real positions; the moon shows its phase
- stars twinkle at night, with the odd shooting star; clouds drift by during the day
- hills with houses whose windows light up after dark

Everything is calculated locally (no internet needed). Works on 64x32 and 32x32.
"""

import math
import os
import random
from datetime import datetime

import numpy as np

from utils import Display, run

LAT = float(os.getenv("SKY_LAT") or 49.87)   # default: Darmstadt
LON = float(os.getenv("SKY_LON") or 8.65)


# --- Astronomy: port of suncalc.js (Vladimir Agafonkin, BSD-2-Clause) ----------------

RAD = math.pi / 180
OBLIQUITY = RAD * 23.4397


def _days(dt):
    """Days since J2000 for a timezone-aware datetime."""
    return dt.timestamp() / 86400 - 0.5 + 2440588 - 2451545


def _right_ascension(l, b):
    return math.atan2(math.sin(l) * math.cos(OBLIQUITY) - math.tan(b) * math.sin(OBLIQUITY), math.cos(l))


def _declination(l, b):
    return math.asin(math.sin(b) * math.cos(OBLIQUITY) + math.cos(b) * math.sin(OBLIQUITY) * math.sin(l))


def _sidereal_time(d, lw):
    return RAD * (280.16 + 360.9856235 * d) - lw


def _sun_coords(d):
    m = RAD * (357.5291 + 0.98560028 * d)
    c = RAD * (1.9148 * math.sin(m) + 0.02 * math.sin(2 * m) + 0.0003 * math.sin(3 * m))
    l = m + c + RAD * 102.9372 + math.pi
    return _declination(l, 0), _right_ascension(l, 0)


def _moon_coords(d):
    l0 = RAD * (218.316 + 13.176396 * d)
    m = RAD * (134.963 + 13.064993 * d)
    f = RAD * (93.272 + 13.229350 * d)
    l = l0 + RAD * 6.289 * math.sin(m)
    b = RAD * 5.128 * math.sin(f)
    dist = 385001 - 20905 * math.cos(m)
    return _declination(l, b), _right_ascension(l, b), dist


def _horizontal(d, dec, ra, lat, lon):
    """(azimuth, altitude) in degrees. Azimuth 0 = south, negative = east, positive = west."""
    h = _sidereal_time(d, -lon * RAD) - ra
    phi = lat * RAD
    az = math.atan2(math.sin(h), math.cos(h) * math.sin(phi) - math.tan(dec) * math.cos(phi))
    alt = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(h))
    return math.degrees(az), math.degrees(alt)


def sun_position(dt, lat=LAT, lon=LON):
    d = _days(dt)
    dec, ra = _sun_coords(d)
    return _horizontal(d, dec, ra, lat, lon)


def moon_position(dt, lat=LAT, lon=LON):
    d = _days(dt)
    dec, ra, _ = _moon_coords(d)
    return _horizontal(d, dec, ra, lat, lon)


def moon_phase(dt):
    """0 = new moon, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter."""
    d = _days(dt)
    s_dec, s_ra = _sun_coords(d)
    m_dec, m_ra, m_dist = _moon_coords(d)
    sun_dist = 149598000
    phi = math.acos(math.sin(s_dec) * math.sin(m_dec) + math.cos(s_dec) * math.cos(m_dec) * math.cos(s_ra - m_ra))
    inc = math.atan2(sun_dist * math.sin(phi), m_dist - sun_dist * math.cos(phi))
    angle = math.atan2(math.cos(s_dec) * math.sin(s_ra - m_ra),
                       math.sin(s_dec) * math.cos(m_dec) - math.cos(s_dec) * math.sin(m_dec) * math.cos(s_ra - m_ra))
    return 0.5 + 0.5 * inc * (-1 if angle < 0 else 1) / math.pi


# --- Colours -----------------------------------------------------------------------

# (sun altitude in degrees, sky colour at the top, sky colour at the horizon).
# Kept moderate: a full panel of bright sky draws a lot of current.
SKY_KEYS = [
    (-18, (2, 3, 12), (4, 6, 22)),
    (-10, (4, 6, 30), (20, 16, 50)),
    (-4, (14, 18, 60), (100, 45, 60)),
    (0, (30, 45, 110), (200, 90, 35)),
    (6, (40, 85, 160), (190, 135, 85)),
    (20, (22, 80, 170), (100, 155, 210)),
]


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def sky_colors(alt):
    if alt <= SKY_KEYS[0][0]:
        return SKY_KEYS[0][1:]
    for (a0, top0, hor0), (a1, top1, hor1) in zip(SKY_KEYS, SKY_KEYS[1:]):
        if alt <= a1:
            t = (alt - a0) / (a1 - a0)
            return _mix(top0, top1, t), _mix(hor0, hor1, t)
    return SKY_KEYS[-1][1:]


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


# --- Mode --------------------------------------------------------------------------

class Sky:
    fps = 10

    def __init__(self, display: Display, now=None):
        self.d = display
        self.now = now or (lambda: datetime.now().astimezone())
        W, H = display.width, display.height
        self.W, self.H = W, H
        self.wide = display.wide
        rng = random.Random(7)

        # Rolling hills: ground height per column
        self.ground = [int(round(3 + 1.3 * math.sin(x * 0.21) + 0.9 * math.sin(x * 0.07 + 1.3))) for x in range(W)]
        self.horizon = H - 4                      # altitude 0 maps here
        self.houses = [10, 46] if self.wide else [22]

        # Stars in the sky above the hills (not behind the clock)
        self.stars = []
        while len(self.stars) < (34 if self.wide else 16):
            x, y = rng.randrange(W), rng.randrange(0, self.horizon - 1)
            if y > 8 or not (W // 2 - 15 <= x <= W // 2 + 15):
                self.stars.append((x, y, rng.uniform(0.5, 1.0), rng.uniform(0, 6.3), rng.uniform(0.6, 1.8)))

        self.clouds = [{"x": rng.uniform(0, W), "y": rng.randint(9, 14), "w": rng.randint(7, 11)}
                       for _ in range(2 if self.wide else 1)]
        self.meteor = None
        self.rng = rng
        self.frame_no = 0
        self.window_flicker = [1.0] * 4
        self._astro_time = None

    # --- positions ---

    def _update_astro(self, now):
        if self._astro_time is None or abs((now - self._astro_time).total_seconds()) > 30:
            self.sun_az, self.sun_alt = sun_position(now)
            self.moon_az, self.moon_alt = moon_position(now)
            self.phase = moon_phase(now)
            self._astro_time = now

    def _to_xy(self, az, alt):
        """Map the sky from north-east (-135) over south (0) to north-west (+135) onto the panel."""
        x = (az + 135) / 270 * (self.W - 1)
        y = self.horizon - alt / 60 * (self.horizon - 3)
        return x, y

    # --- drawing ---

    def frame(self):
        now = self.now()
        self._update_astro(now)
        W, H = self.W, self.H
        alt = self.sun_alt
        daylight = clamp((alt + 6) / 12)          # 0 at night, 1 in daytime
        night = clamp((-alt - 4) / 10)            # stars fade in below -4 deg
        t = self.frame_no / self.fps

        # Sky gradient
        top, hor = sky_colors(alt)
        rows = np.linspace(0, 1, self.horizon + 1) ** 1.6
        img = np.zeros((H, W, 3), dtype=np.float32)
        for y in range(H):
            img[y, :] = _mix(top, hor, rows[min(y, self.horizon)])

        # Glow around the sun (also just below the horizon at dawn and dusk)
        sx, sy = self._to_xy(self.sun_az, alt)
        if alt > -8:
            yy, xx = np.mgrid[0:H, 0:W]
            radius = 14 if self.wide else 9
            dist = np.sqrt((xx - sx) ** 2 + ((yy - sy) * 1.3) ** 2)
            strength = np.clip(1 - dist / radius, 0, 1) ** 2 * clamp((alt + 8) / 8) * 0.6
            img += strength[..., None] * np.array([255, 150, 60], dtype=np.float32) * (1 - 0.5 * daylight)

        # Stars
        if night > 0:
            for x, y, base, phase, speed in self.stars:
                b = 255 * night * base * (0.65 + 0.35 * math.sin(t * speed + phase))
                img[y, x] = np.maximum(img[y, x], (b, b, b * 0.95))
            self._draw_meteor(img, night)

        # Moon (visible by day too, just fainter)
        if self.moon_alt > -1:
            mx, my = self._to_xy(self.moon_az, self.moon_alt)
            self._draw_moon(img, mx, my, 0.55 + 0.45 * (1 - daylight))

        # Sun
        if alt > -2:
            r = 2 if self.wide else 1
            color = _mix((255, 110, 40), (255, 225, 120), clamp(alt / 12))
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r + 0.5:
                        self._put(img, round(sx) + dx, round(sy) + dy, color)

        self._draw_clouds(img, daylight, hor)
        self._draw_ground(img, daylight)

        self.d.image(np.clip(img, 0, 255).astype(np.uint8))

        # Clock: dark on a bright sky, soft white at night
        brightness = 0.3 * top[0] + 0.6 * top[1] + 0.1 * top[2]
        color = (10, 14, 40) if brightness > 60 else (190, 190, 210)
        time_str = now.strftime("%H:%M")
        width = self.d.text_width(self.d.font_large, time_str)
        self.d.text(self.d.font_large, (W - width + 1) // 2, 6, color, time_str)

        self.frame_no += 1

    def _put(self, img, x, y, color, alpha=1.0):
        if 0 <= x < self.W and 0 <= y < self.H:
            img[y, x] = img[y, x] * (1 - alpha) + np.array(color, dtype=np.float32) * alpha

    def _draw_moon(self, img, cx, cy, brightness):
        r = 3 if self.wide else 2
        k = math.cos(2 * math.pi * self.phase)
        waxing = self.phase < 0.5
        lit = tuple(c * brightness for c in (225, 225, 195))
        dark = (16, 16, 26)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r + 0.5:
                    continue
                nx, ny = dx / (r + 0.5), dy / (r + 0.5)
                edge = k * math.sqrt(max(0.0, 1 - ny * ny))
                is_lit = nx > edge if waxing else nx < -edge
                if is_lit:
                    self._put(img, round(cx) + dx, round(cy) + dy, lit)
                else:  # the dark side only dims the sky a little, like on the real moon
                    self._put(img, round(cx) + dx, round(cy) + dy, dark, 0.4)

    def _draw_meteor(self, img, night):
        if self.meteor is None and night > 0.8 and self.rng.random() < 1 / 1200:
            self.meteor = {"x": self.rng.uniform(5, self.W - 5), "y": self.rng.uniform(1, 6),
                           "dx": self.rng.choice([-1.6, 1.6]), "dy": 0.7, "life": 9}
        m = self.meteor
        if m:
            for i in range(5):
                fade = (1 - i / 5) * min(1.0, m["life"] / 4)
                self._put(img, round(m["x"] - m["dx"] * i * 0.6), round(m["y"] - m["dy"] * i * 0.6),
                          (255, 255, 230), fade)
            m["x"] += m["dx"]
            m["y"] += m["dy"]
            m["life"] -= 1
            if m["life"] <= 0:
                self.meteor = None

    def _draw_clouds(self, img, daylight, horizon_color):
        color = _mix((28, 28, 40), _mix((235, 235, 245), horizon_color, 0.25), daylight)
        alpha = 0.12 + 0.73 * daylight
        for c in self.clouds:
            c["x"] = (c["x"] + 0.025) % (self.W + c["w"] * 2)
            x0 = c["x"] - c["w"]
            for dx in range(c["w"]):
                bump = 1.6 if c["w"] * 0.25 < dx < c["w"] * 0.65 else 1.0
                half = (1 - ((dx - c["w"] / 2) / (c["w"] / 2)) ** 2) * bump * 1.6
                for dy in range(-2, 2):
                    if -half <= dy <= half * 0.6:
                        self._put(img, round(x0 + dx), c["y"] + dy, color, alpha)

    def _draw_ground(self, img, daylight):
        H = self.H
        ground = _mix((4, 8, 6), (22, 62, 28), daylight)
        for x, h in enumerate(self.ground):
            img[H - h:, x] = ground
        house, roof = _mix((10, 10, 14), (70, 55, 50), daylight), _mix((14, 12, 16), (110, 45, 40), daylight)
        lights_on = daylight < 0.5
        for i, hx in enumerate(self.houses):
            base = H - max(self.ground[hx:hx + 5])
            for dx in range(5):
                for dy in range(1, 4):
                    self._put(img, hx + dx, base - dy, house)
            for dx in range(-1, 6):
                self._put(img, hx + dx, base - 4, roof)
            for dx in range(1, 4):
                self._put(img, hx + dx, base - 5, roof)
            if lights_on:
                if self.frame_no % 7 == 0:
                    self.window_flicker[i] = self.rng.uniform(0.75, 1.0)
                level = self.window_flicker[i] * (1 - daylight * 1.6)
                self._put(img, hx + 1, base - 2, tuple(c * level for c in (255, 190, 70)))
                self._put(img, hx + 3, base - 2, tuple(c * level for c in (255, 190, 70)))


if __name__ == "__main__":
    run(Sky)
