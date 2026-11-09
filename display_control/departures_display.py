#!/usr/bin/env python3
"""
Departures mode: next buses/trams/trains from an RMV stop, with real-time minutes.

64 wide: clock, then 3 rows of  [icon] line  direction-label  minutes
32x32:   clock, then 3 rows of  [icon] line  minutes   (line colour = direction)

Minutes are yellow when the departure is late, and "X" in red when it's cancelled.
Departures you can't reach in time (RMV_WALK_MINUTES) are left out.
"""

import math
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from utils import Display, IconBus, IconTrain, IconTram, run

API_URL = "https://www.rmv.de/hapi/departureBoard"
TOKEN = os.getenv("RMV_ACCESS_TOKEN")
STATION_ID = os.getenv("RMV_STATION_ID") or "3004736"
# "id:label,id:label" - only departures heading via these stops. Empty = all departures.
DIRECTIONS = [d.split(":", 1) for d in os.getenv("RMV_DIRECTIONS", "3024730:Hbf,3004734:LiWi").split(",")
              if ":" in d]
WALK_MINUTES = int(os.getenv("RMV_WALK_MINUTES") or 2)
POLL_SECONDS = int(os.getenv("RMV_POLL_SECONDS") or 90)
RMV_TZ = ZoneInfo("Europe/Berlin")  # RMV times are German local time, whatever the Pi's TZ

DIRECTION_COLORS = [(255, 255, 255), (120, 200, 255), (255, 170, 220), (180, 255, 160)]
LATE_COLOR = (255, 200, 0)
CANCELLED_COLOR = (255, 40, 40)
LABEL_COLOR = (150, 150, 150)


@dataclass
class Departure:
    line: str
    category: str               # RMV catOut, e.g. "Bus", "Tram", "S", "RB"
    direction: str               # destination text from RMV
    label: str                   # our short label (from RMV_DIRECTIONS)
    label_index: int
    planned: datetime
    realtime: Optional[datetime]
    cancelled: bool

    @property
    def expected(self):
        return self.realtime or self.planned

    @property
    def delay_minutes(self):
        return round((self.expected - self.planned).total_seconds() / 60)

    def minutes_from(self, now):
        return math.floor((self.expected - now).total_seconds() / 60)


def parse_departure(obj, label="", label_index=0):
    product = obj.get("Product")
    if isinstance(product, list):
        product = product[0]
    product = product or {}
    planned = datetime.strptime(f'{obj["date"]} {obj["time"]}', "%Y-%m-%d %H:%M:%S")
    realtime = None
    if obj.get("rtTime"):
        rt_date = obj.get("rtDate", obj["date"])
        realtime = datetime.strptime(f'{rt_date} {obj["rtTime"]}', "%Y-%m-%d %H:%M:%S").replace(tzinfo=RMV_TZ)
    return Departure(
        line=(product.get("line") or product.get("displayNumber") or obj.get("name", "?")).strip(),
        category=(product.get("catOut") or "").strip(),
        direction=obj.get("direction", "").strip(),
        label=label,
        label_index=label_index,
        planned=planned.replace(tzinfo=RMV_TZ),
        realtime=realtime,
        cancelled=bool(obj.get("cancelled")),
    )


class DepartureSource:
    """Polls the RMV API in a background thread."""

    def __init__(self):
        self.departures = []
        self.error = None if TOKEN else "No RMV key"
        self.updated = None

    def fetch(self):
        departures = []
        for index, (direction_id, label) in enumerate(DIRECTIONS or [(None, "")]):
            params = {"accessId": TOKEN, "id": STATION_ID, "format": "json",
                      "duration": 120, "maxJourneys": 20}
            if direction_id:
                params["direction"] = direction_id
            data = requests.get(API_URL, params=params, timeout=10).json()
            if "errorCode" in data:
                raise RuntimeError(f'{data["errorCode"]}: {data.get("errorText", "")}')
            departures += [parse_departure(o, label, index) for o in data.get("Departure", [])]
        # A line can serve several configured directions; show it once
        unique = {(d.line, d.planned, d.direction): d for d in departures}
        return sorted(unique.values(), key=lambda d: d.expected)

    def poll_forever(self):
        while True:
            try:
                self.departures = self.fetch()
                self.error = None
                self.updated = time.time()
            except Exception as e:
                print(f"RMV error: {e}", flush=True)
                # Keep showing the last data for a while; times are absolute, so it stays correct
                if self.updated is None or time.time() - self.updated > 15 * 60:
                    self.error = "RMV error" if "API_AUTH" not in str(e) else "RMV key bad"
            time.sleep(POLL_SECONDS)

    def start(self):
        if TOKEN:
            threading.Thread(target=self.poll_forever, daemon=True).start()
        return self


def icon_for(category):
    c = category.lower()
    if c in ("tram", "str"):
        return IconTram
    if c == "bus" or c.startswith("bus"):
        return IconBus
    return IconTrain


class Departures:
    fps = 2
    rows = 3

    def __init__(self, display: Display, source=None):
        self.d = display
        self.source = source or DepartureSource().start()

    def upcoming(self, now):
        return [d for d in self.source.departures
                if d.cancelled or d.minutes_from(now) >= WALK_MINUTES][:self.rows]

    def frame(self):
        d = self.d
        if self.source.error:
            d.error(self.source.error)
            return
        now = datetime.now(RMV_TZ)
        d.clear()
        d.clock()
        departures = self.upcoming(now)
        if not departures:
            msg = "Loading" if self.source.updated is None and TOKEN else "No departures"
            d.text(d.font_small, 0, 20, LABEL_COLOR, msg)
            return
        for i, dep in enumerate(departures):
            self._draw_row(8 + i * 8, dep, now)

    def _draw_row(self, y, dep, now):
        d = self.d
        icon_for(dep.category)(d, 0, y).draw()

        if dep.cancelled:
            minutes, color = "X", CANCELLED_COLOR
        else:
            m = dep.minutes_from(now)
            minutes = str(m) if m < 100 else "99+"
            color = LATE_COLOR if dep.delay_minutes >= 2 else (255, 255, 255)
        minutes_font = d.font_large if d.wide else d.font_small
        minutes_x = d.width - d.text_width(minutes_font, minutes)
        d.text(minutes_font, minutes_x, y + 7, color, minutes)

        if d.wide:
            line_font = d.font_large if len(dep.line) <= 3 else d.font_small
            d.text(line_font, 9, y + 7, (255, 255, 255), dep.line)
            label = dep.label or dep.direction
            label_x = 27
            max_chars = max(0, (minutes_x - 2 - label_x) // 4)
            d.text(d.font_small, label_x, y + 6, LABEL_COLOR, label[:max_chars])
        else:
            line_color = DIRECTION_COLORS[dep.label_index % len(DIRECTION_COLORS)]
            d.text(d.font_small, 9, y + 6, line_color, dep.line[:3])


if __name__ == "__main__":
    run(Departures)
