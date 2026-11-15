#!/usr/bin/env python3
"""
Sky clock: the real sky over SKY_LAT/SKY_LON, with the clock on top.

- sky colours follow the sun's altitude (night, dawn/dusk pink and orange, day blue)
- the sun and moon move across the sky to their real positions; the moon shows its phase
- stars twinkle at night, with the odd shooting star
- a hint of the current weather from Open-Meteo (free, no key): more and greyer clouds when
  it's cloudy, light rain or snow, fog and lightning. The sky itself stays blue.
  Without internet: a few fair clouds.
- hills with houses and trees; the windows light up after dark

Sun and moon are calculated locally. Works on 64x32 and 32x32.
Settings: SKY_LAT / SKY_LON, SKY_WEATHER=0 to turn weather off.
"""

import math
import os
import random
import threading
import time
from datetime import datetime

import numpy as np
import requests
from PIL import Image

from utils import Display, run

LAT = float(os.getenv("SKY_LAT") or 49.87)   # default: Darmstadt
LON = float(os.getenv("SKY_LON") or 8.65)
WEATHER_ON = (os.getenv("SKY_WEATHER") or "1") != "0"


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


# --- Weather -----------------------------------------------------------------------

FAIR = {"clouds": 0.25, "rain": 0.0, "snow": 0.0, "fog": False, "thunder": False, "wind": 10.0}


def weather_from_open_meteo(current):
    """Turn Open-Meteo 'current' values into what the sky draws."""
    code = int(current.get("weather_code") or 0)
    precipitation = float(current.get("precipitation") or 0)
    snowing = code in (71, 73, 75, 77, 85, 86) or float(current.get("snowfall") or 0) > 0
    raining = code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99)
    # Drizzle codes often come with 0.0 mm, so give every rain/snow code a minimum intensity
    intensity = max(precipitation, {51: .2, 53: .4, 55: .7, 61: .5, 63: 1.5, 65: 4, 80: .8,
                                    81: 2, 82: 5, 71: .3, 73: .8, 75: 2, 85: .5, 86: 1.5}.get(code, .5))
    return {
        "clouds": clamp(float(current.get("cloud_cover") or 0) / 100),
        "rain": intensity if raining and not snowing else 0.0,
        "snow": intensity if snowing else 0.0,
        "fog": code in (45, 48),
        "thunder": code in (95, 96, 99),
        "wind": float(current.get("wind_speed_10m") or 10),
    }


class Weather:
    """Polls Open-Meteo every 15 minutes in the background. .now is always usable."""

    URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self):
        self.now = dict(FAIR)
        if WEATHER_ON:
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                r = requests.get(self.URL, timeout=15, params={
                    "latitude": LAT, "longitude": LON,
                    "current": "cloud_cover,precipitation,snowfall,weather_code,wind_speed_10m"})
                self.now = weather_from_open_meteo(r.json()["current"])
                print(f"Weather: {self.now}", flush=True)
                time.sleep(900)
            except Exception as e:
                print(f"Weather unavailable ({e!r}), retrying in 2 min", flush=True)
                time.sleep(120)


def cloud_texture(width, height, seed=3):
    """Soft noise that wraps around horizontally, for clouds drifting across forever."""
    rng = np.random.default_rng(seed)
    total = np.zeros((height, width), dtype=np.float32)
    for cell_x, cell_y, weight in ((24, 10, 1.0), (12, 5, 0.5), (6, 3, 0.25)):
        gw, gh = max(2, width // cell_x), max(2, height // cell_y + 2)
        grid = rng.random((gh, gw)).astype(np.float32)
        tiled = np.tile(grid, (1, 3))
        big = Image.fromarray(tiled).resize((width * 3, height + 2 * cell_y), Image.BICUBIC)
        total += weight * np.asarray(big)[cell_y:cell_y + height, width:2 * width]
    total -= total.min()
    return total / total.max()


# --- Mode --------------------------------------------------------------------------

class Sky:
    fps = 10

    def __init__(self, display: Display, now=None, weather=None):
        self.d = display
        self.now = now or (lambda: datetime.now().astimezone())
        self.weather = weather or Weather()
        W, H = display.width, display.height
        self.W, self.H = W, H
        self.wide = display.wide
        rng = random.Random(7)

        # Gentle hills: ground height per column
        self.ground = [int(round(3 + 1.1 * math.sin(x * 0.19) + 0.8 * math.sin(x * 0.07 + 1.3))) for x in range(W)]
        self.horizon = H - 4                      # altitude 0 maps here
        # (x, width, wall height) of each house, and x of each tree
        self.houses = [(8, 6, 3), (15, 4, 4), (47, 5, 3)] if self.wide else [(18, 6, 3)]
        self.trees = [5, 22, 41, 56] if self.wide else [6, 27]

        # Stars in the sky above the hills (not behind the clock)
        self.stars = []
        while len(self.stars) < (34 if self.wide else 16):
            x, y = rng.randrange(W), rng.randrange(0, self.horizon - 1)
            if y > 8 or not (W // 2 - 15 <= x <= W // 2 + 15):
                self.stars.append((x, y, rng.uniform(0.5, 1.0), rng.uniform(0, 6.3), rng.uniform(0.6, 1.8)))

        self.texture_w = W * 4
        self.texture = cloud_texture(self.texture_w, H)
        self.cloud_x = 0.0
        self._threshold_for = None
        self.drops = []
        self.flash = 0
        self.meteor = None
        self.rng = rng
        self.frame_no = 0
        self.window_flicker = [1.0] * len(self.houses)
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
        w = self.weather.now
        W, H = self.W, self.H
        alt = self.sun_alt
        daylight = clamp((alt + 6) / 12)          # 0 at night, 1 in daytime
        night = clamp((-alt - 4) / 10)            # stars fade in below -4 deg
        t = self.frame_no / self.fps
        # How grey it is outside (0..1). Only used as a hint: the sky stays blue.
        overcast = clamp(clamp((w["clouds"] - 0.55) / 0.4) + (0.3 if w["rain"] or w["snow"] else 0))

        # Sky gradient, greyer and darker under heavy cloud
        top, hor = sky_colors(alt)
        top, hor = self._overcast(top, overcast * 0.2), self._overcast(hor, overcast * 0.2)
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
            strength = np.clip(1 - dist / radius, 0, 1) ** 2 * clamp((alt + 8) / 8) * 0.6 * (1 - 0.4 * overcast)
            img += strength[..., None] * np.array([255, 150, 60], dtype=np.float32) * (1 - 0.5 * daylight)

        # Stars
        if night > 0:
            for x, y, base, phase, speed in self.stars:
                b = 255 * night * base * (0.65 + 0.35 * math.sin(t * speed + phase))
                img[y, x] = np.maximum(img[y, x], (b, b, b * 0.95))
            if w["clouds"] < 0.5:
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

        self._draw_clouds(img, w, daylight, hor, overcast)
        if w["fog"]:
            img = img * 0.45 + np.array(_mix((18, 18, 24), (150, 150, 155), daylight), dtype=np.float32) * 0.55
        self._draw_precipitation(img, w, daylight)
        self._draw_ground(img, daylight, overcast)
        self._lightning(img, w)

        self.d.image(np.clip(img, 0, 255).astype(np.uint8))
        self._draw_clock(now, top, daylight)
        self.frame_no += 1

    @staticmethod
    def _overcast(color, amount):
        grey = (0.3 * color[0] + 0.55 * color[1] + 0.15 * color[2]) * 0.55   # dull and darker
        return _mix(color, (grey, grey * 1.02, grey * 1.1), amount * 0.9)

    def _put(self, img, x, y, color, alpha=1.0):
        if 0 <= x < self.W and 0 <= y < self.H:
            img[y, x] = img[y, x] * (1 - alpha) + np.array(color, dtype=np.float32) * alpha

    def _draw_clock(self, now, top, daylight):
        """White HH:MM, slightly dimmer at night; a soft dark outline keeps it readable on a bright sky."""
        d = self.d
        time_str = now.strftime("%H:%M")
        x = (self.W - d.text_width(d.font_large, time_str) + 1) // 2
        if daylight > 0.05:
            outline = tuple(int(c * 0.35) for c in top)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                d.text(d.font_large, x + dx, 6 + dy, outline, time_str)
        level = 0.72 + 0.28 * daylight
        d.text(d.font_large, x, 6, (int(255 * level), int(255 * level), int(250 * level)), time_str)

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

    def _draw_clouds(self, img, w, daylight, horizon_color, overcast):
        if w["clouds"] <= 0.02:
            return
        cover = 0.08 + 0.32 * w["clouds"]            # at most ~40 % of the sky, so the blue stays
        if self._threshold_for != cover:          # threshold so that `cover` of the sky is cloud
            self.threshold = float(np.quantile(self.texture, 1 - cover))
            self._threshold_for = cover
        self.cloud_x = (self.cloud_x + 0.015 + w["wind"] / 900) % self.texture_w
        x0 = int(self.cloud_x)
        cols = (np.arange(self.W) + x0) % self.texture_w
        frac = self.cloud_x - x0
        n = self.texture[:, cols] * (1 - frac) + self.texture[:, (cols + 1) % self.texture_w] * frac
        density = np.clip((n - self.threshold + 0.04) / 0.14, 0, 1)
        # Light, white clouds when fair; grey, heavy ones when it's overcast or raining
        bright = _mix((245, 245, 250), (150, 154, 165), overcast)
        bright = _mix(bright, horizon_color, 0.2 * (1 - daylight) + 0.15)
        color = np.array(_mix((26, 27, 36), bright, daylight), dtype=np.float32)
        shade = 0.82 + 0.18 * np.clip((n - self.threshold) / 0.25, 0, 1)   # thicker = brighter tops
        alpha = (density * (0.55 + 0.4 * daylight))[..., None]
        img[:] = img * (1 - alpha) + (color * shade[..., None]) * alpha

    def _draw_precipitation(self, img, w, daylight):
        snow, rain = w["snow"], w["rain"]
        # A light sprinkle, a bit more when it pours
        target = int(self.W * 0.3 * min(1.0, 0.4 + max(rain, snow) / 4)) if (rain or snow) else 0
        while len(self.drops) < target:
            self.drops.append([self.rng.uniform(0, self.W), self.rng.uniform(-self.H, 0), self.rng.uniform(0, 6.3)])
        del self.drops[target:]
        if snow:
            color = _mix((70, 70, 80), (235, 235, 245), daylight)
        else:
            color = _mix((70, 85, 120), (175, 200, 245), daylight)
        for drop in self.drops:
            if snow:
                drop[1] += 0.25
                drop[0] += 0.15 * math.sin(self.frame_no / 8 + drop[2])
                self._put(img, round(drop[0]) % self.W, round(drop[1]), color, 0.9)
            else:
                drop[1] += 1.6
                drop[0] += 0.25
                for i in range(3):
                    self._put(img, round(drop[0] - 0.15 * i) % self.W, round(drop[1]) - i, color, 0.95 - 0.3 * i)
            if drop[1] >= self.H:
                drop[0], drop[1] = self.rng.uniform(0, self.W), self.rng.uniform(-6, 0)

    def _lightning(self, img, w):
        if w["thunder"] and self.flash == 0 and self.rng.random() < 1 / 250:
            self.flash = 3
        if self.flash:
            img += (90, 90, 110) if self.flash != 2 else (25, 25, 30)
            self.flash -= 1

    def _draw_ground(self, img, daylight, overcast):
        H = self.H
        dim = 1 - 0.1 * overcast
        ground = _mix((4, 8, 6), (26 * dim, 66 * dim, 30 * dim), daylight)
        for x, h in enumerate(self.ground):
            img[H - h:, x] = ground
        tree = _mix((3, 9, 5), (18 * dim, 52 * dim, 24 * dim), daylight)
        for tx in self.trees:
            base = H - self.ground[tx]
            for dx, dy in ((0, 1), (0, 2), (-1, 3), (0, 3), (1, 3), (-1, 4), (0, 4), (1, 4), (0, 5)):
                self._put(img, tx + dx, base - dy, tree)
        wall = _mix((9, 9, 13), (105 * dim, 96 * dim, 86 * dim), daylight)   # warm stone
        roof = _mix((6, 6, 10), (52 * dim, 58 * dim, 72 * dim), daylight)    # slate grey
        glass = _mix((6, 6, 10), (24, 32, 46), daylight)
        lights_on = daylight < 0.5
        for i, (hx, hw, hh) in enumerate(self.houses):
            base = H - max(self.ground[hx:hx + hw])
            for dx in range(hw):
                for dy in range(1, hh + 1):
                    self._put(img, hx + dx, base - dy, wall)
            for row in range((hw + 1) // 2 + 1):        # gable roof, one pixel wider than the walls
                for dx in range(-1 + row, hw + 1 - row):
                    self._put(img, hx + dx, base - hh - 1 - row, roof)
            if self.frame_no % 7 == 0:
                self.window_flicker[i] = self.rng.uniform(0.8, 1.0)
            level = self.window_flicker[i] * clamp(1 - daylight * 2)
            for wx in range(1, hw - 1, 2):
                color = tuple(c * level for c in (255, 185, 80)) if lights_on and (i + wx) % 3 else glass
                self._put(img, hx + wx, base - 2, color)


if __name__ == "__main__":
    run(Sky)
