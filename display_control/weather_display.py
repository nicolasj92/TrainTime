#!/usr/bin/env python3
"""
Weather mode: the next hours at a glance, for SKY_LAT / SKY_LON (set on the System page).

- top: weather icon, current temperature, today's high/low (and the clock on 64x32)
- bottom: temperature curve for the next hours, coloured from cold blue to warm orange,
  night hours shaded, rain chance as a blue band along the bottom edge

Data from Open-Meteo (free, no key), refreshed every 15 minutes.
"""

import math
import os
import threading
import time
from datetime import datetime

import numpy as np
import requests

from utils import Display, run

LAT = float(os.getenv("SKY_LAT") or 49.87)
LON = float(os.getenv("SKY_LON") or 8.65)
URL = "https://api.open-meteo.com/v1/forecast"


class Forecast:
    """Polls Open-Meteo in the background. .data is None until the first answer arrives."""

    def __init__(self):
        self.data = None
        self.error = None
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                r = requests.get(URL, timeout=15, params={
                    "latitude": LAT, "longitude": LON, "timezone": "auto", "forecast_days": 2,
                    "current": "temperature_2m,weather_code,is_day",
                    "hourly": "temperature_2m,precipitation_probability,is_day",
                    "daily": "temperature_2m_max,temperature_2m_min"})
                self.data = parse(r.json())
                self.error = None
                time.sleep(900)
            except Exception as e:
                print(f"Weather unavailable ({e!r}), retrying in 2 min", flush=True)
                self.error = "No weather"
                time.sleep(120)


def parse(raw, now=None):
    """Open-Meteo JSON -> the values this mode draws, starting at the current hour."""
    hourly = raw["hourly"]
    now = now or datetime.now()
    stamp = now.strftime("%Y-%m-%dT%H:00")
    start = hourly["time"].index(stamp) if stamp in hourly["time"] else 0
    cur = raw["current"]
    return {
        "temp": cur["temperature_2m"],
        "code": int(cur["weather_code"]),
        "day": bool(cur["is_day"]),
        "high": raw["daily"]["temperature_2m_max"][0],
        "low": raw["daily"]["temperature_2m_min"][0],
        "hours": [{"temp": t, "rain": (p or 0) / 100, "day": bool(d), "hour": int(ts[11:13])}
                  for t, p, d, ts in zip(hourly["temperature_2m"][start:], hourly["precipitation_probability"][start:],
                                         hourly["is_day"][start:], hourly["time"][start:])],
    }


# --- Icons (11x9). Letters pick colours, "." is empty ----------------------------------

SUN = ["...y...y...", "....yyy....", "..yYYYYYy..", ".yYYYYYYYy.", "yyYYYYYYYyy",
       ".yYYYYYYYy.", "..yYYYYYy..", "....yyy....", "...y...y..."]
MOON = ["....MMM....", "...MMM.....", "..MMM......", "..MMM......", "..MMM......",
        "..MMMM.....", "...MMMMM.M.", "....MMMMM..", "..........."]
CLOUD = ["...........", "....WWW....", "..WWWWWW...", ".WWWWWWWWW.", "WWWWWWWWWWW",
         "WWWWWWWWWWW", ".WWWWWWWWW.", "...........", "..........."]
PARTLY = ["..y.y......", "...YYY.....", ".yYYYWWW...", "..YYWWWWW..", ".yYWWWWWWWW",
          "..WWWWWWWWW", "..WWWWWWWWW", "...WWWWWWW.", "..........."]
RAIN = ["....GGG....", "..GGGGGG...", ".GGGGGGGGG.", "GGGGGGGGGGG", ".GGGGGGGGG.",
        "..b..b..b..", ".b..b..b...", "...b..b..b.", "..b..b....."]
SNOW = ["....GGG....", "..GGGGGG...", ".GGGGGGGGG.", "GGGGGGGGGGG", ".GGGGGGGGG.",
        "..s...s....", "....s...s..", ".s...s.....", "...s...s..."]
STORM = ["....DDD....", "..DDDDDD...", ".DDDDDDDDD.", "DDDDDDDDDDD", ".DDDYYDDDD.",
         "....YY.....", "...YYYY....", ".....Y.....", "....Y......"]
FOG = ["...........", ".FFFFFFFFF.", "...........", "FFFFFFFFFF.", "...........",
       ".FFFFFFFFFF", "...........", "FFFFFFFFF..", "..........."]

ICON_COLORS = {"y": (230, 150, 20), "Y": (255, 200, 40), "M": (220, 220, 190), "W": (225, 228, 238),
               "G": (150, 155, 170), "D": (95, 100, 115), "b": (70, 150, 255), "s": (240, 240, 255),
               "F": (150, 150, 160)}


def icon_for(code, day):
    if code in (95, 96, 99):
        return STORM
    if code in (71, 73, 75, 77, 85, 86):
        return SNOW
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return RAIN
    if code in (45, 48):
        return FOG
    if code == 3:
        return CLOUD
    if code in (1, 2):
        return PARTLY if day else CLOUD
    return SUN if day else MOON


def temp_color(t):
    """Cold blue -> cool cyan -> mild green-yellow -> warm orange -> hot red."""
    stops = [(-10, (90, 120, 255)), (0, (80, 190, 255)), (10, (120, 220, 140)),
             (18, (240, 210, 70)), (26, (255, 140, 40)), (34, (255, 60, 40))]
    if t <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return tuple(a + (b - a) * k for a, b in zip(c0, c1))
    return stops[-1][1]


class Weather:
    fps = 10

    def __init__(self, display: Display, source=None):
        self.d = display
        self.source = source or Forecast()
        self.W, self.H = display.width, display.height
        self.frame_no = 0

    def frame(self):
        d, data = self.d, self.source.data
        if data is None:
            if self.source.error:
                d.error(self.source.error)
            else:
                d.clear()
                d.text(d.font_small, 1, 18, (150, 150, 160), "Loading…" if d.wide else "Wait…")
            return
        img = np.zeros((self.H, self.W, 3), dtype=np.float32)
        top = 16 if d.wide else 15
        self._draw_curve(img, data["hours"], top, self.H - 4)
        self._draw_icon(img, icon_for(data["code"], data["day"]), 0, 1)
        d.image(np.clip(img, 0, 255).astype(np.uint8))

        temp = f"{round(data['temp'])}°"
        d.text(d.font_large, 13, 8, temp_color(data["temp"]), temp)
        hi_lo = f"{round(data['high'])}°/{round(data['low'])}°"
        if d.wide:
            d.text(d.font_small, 13, 15, (140, 140, 155), hi_lo)
            clock = d.time_str()
            d.text(d.font_large, self.W - d.text_width(d.font_large, clock), 8, (170, 170, 185), clock)
        self.frame_no += 1

    def _draw_icon(self, img, rows, x0, y0):
        pulse = 0.8 + 0.2 * math.sin(self.frame_no / 6)
        drop = (self.frame_no // 4) % 2                 # rain and snow move down a pixel and back
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch not in ICON_COLORS:
                    continue
                color = np.array(ICON_COLORS[ch], dtype=np.float32)
                y = y0 + dy
                if ch == "y":
                    color *= pulse
                if ch in "bs":
                    y += drop
                if 0 <= y < self.H:
                    img[y, x0 + dx] = color

    def _draw_curve(self, img, hours, top, bottom):
        """Temperature over the next hours (one column per pixel), area shaded below the line."""
        span = 24 if self.d.wide else 16
        hours = hours[:span + 1]
        if len(hours) < 2:
            return
        temps = [h["temp"] for h in hours]
        lo, hi = min(temps), max(temps)
        if hi - lo < 4:                                 # keep small changes from looking dramatic
            mid = (hi + lo) / 2
            lo, hi = mid - 2, mid + 2
        per_col = (len(hours) - 1) / (self.W - 1)
        for x in range(self.W):
            pos = x * per_col
            i = min(int(pos), len(hours) - 2)
            k = pos - i
            t = temps[i] * (1 - k) + temps[i + 1] * k
            y = bottom - (t - lo) / (hi - lo) * (bottom - top)
            color = np.array(temp_color(t), dtype=np.float32)
            night = not hours[round(pos)]["day"]
            if night:                                   # faint blue for night hours
                img[top - 1:bottom + 1, x] = (4, 5, 16)
            yi = int(round(y))
            img[yi, x] = color
            for yy in range(yi + 1, bottom + 1):        # soft fill under the line
                img[yy, x] = color * (0.28 - 0.18 * (yy - yi) / max(1, bottom - yi))
            rain = hours[i]["rain"] * (1 - k) + hours[i + 1]["rain"] * k
            if rain > 0.1:                              # rain chance along the bottom edge
                img[self.H - 2:, x] = np.array((40, 110, 255), dtype=np.float32) * min(1.0, rain) * 0.9
            if hours[round(pos)]["hour"] in (0, 6, 12, 18) and abs(pos - round(pos)) < per_col / 2:
                img[bottom + 1, x] = (55, 55, 65)       # tick every 6 hours


if __name__ == "__main__":
    run(Weather)
