#!/usr/bin/env python3
"""
Power Flow mode: live solar / grid / house power from Home Assistant.

64 wide: clock, sun, house and grid icons with animated flow lines between them.
32x32:   three rows (solar, house, grid) with values; grid is green when feeding in.
"""

import os
import threading
import time

import requests

from utils import Display, IconGrid, IconHouse, IconSun, run

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


def line_points(x0, y0, x1, y1):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    points = []
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return points
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class PowerFlow:
    fps = 25
    base_color = (60, 100, 160)
    flow_color = (110, 170, 255)

    def __init__(self, display: Display, source=None):
        self.d = display
        self.source = source or PowerSource().start()
        self.flow_tick = 0
        self.flow_phase = 0

    def frame(self):
        s = self.source
        if s.error and not (s.solar or s.grid):
            self.d.error(s.error)
            return
        self.d.clear()
        if self.d.wide:
            self._draw_wide(s.solar, s.home, s.grid)
        else:
            self._draw_compact(s.solar, s.home, s.grid)
        self.flow_tick = (self.flow_tick + 1) % 1000
        if self.flow_tick % 3 == 0:
            self.flow_phase = (self.flow_phase + 1) % 6

    # --- layouts ---

    def _draw_flow(self, start, end, tip_direction):
        d = self.d
        points = line_points(*start, *end)
        for px, py in points:
            d.set_pixel(px, py, *self.base_color)
        for offset in range(0, len(points), 6):
            px, py = points[(offset + self.flow_phase) % len(points)]
            d.set_pixel(px, py, *self.flow_color)
        x, y = end
        tip = {
            "down": [(x, y), (x - 1, y - 1), (x + 1, y - 1)],
            "left": [(x, y), (x + 1, y - 1), (x + 1, y + 1)],
            "right": [(x, y), (x - 1, y - 1), (x - 1, y + 1)],
        }[tip_direction]
        for px, py in tip:
            d.set_pixel(px, py, *self.base_color)

    def _draw_wide(self, solar, home, grid):
        d = self.d
        font = d.font_large
        grid_x, grid_y = 12, 18
        home_x, home_y = 52, 18

        d.text(font, 0, 6, d.white, d.time_str())

        solar_text = f"{solar}W"
        solar_text_x = d.width - len(solar_text) * 6
        IconSun(d, solar_text_x - 12, 0).draw()
        d.text(font, solar_text_x, 6, d.white, solar_text)

        IconHouse(d, home_x + 2, 14).draw()
        IconGrid(d, grid_x - 8, 14).draw()

        home_text = f"{home}W"
        d.text(font, d.width - len(home_text) * 6, home_y + 12, d.white, home_text)
        d.text(font, grid_x - 8, grid_y + 12, d.white, f"{abs(grid)}W")

        solar_anchor = (solar_text_x - 8, 4)
        home_anchor = (home_x + 6, 18)
        grid_anchor = (grid_x - 4, 18)
        if min(solar, home) > 0:
            self._draw_flow(solar_anchor, home_anchor, "down")
        if max(0, solar - home) > 0:
            self._draw_flow(solar_anchor, grid_anchor, "left")
        if max(0, home - solar) > 0:
            self._draw_flow(grid_anchor, home_anchor, "right")

    def _draw_compact(self, solar, home, grid):
        d = self.d
        font = d.font_small
        exporting = grid < 0
        rows = [
            (IconSun, solar, (255, 200, 80)),
            (IconHouse, home, (255, 255, 255)),
            (IconGrid, abs(grid), (90, 220, 120) if exporting else (255, 150, 60)),
        ]
        for i, (icon, value, color) in enumerate(rows):
            y = i * 11
            icon(d, 0, y).draw()
            text = f"{value}W" if value < 10000 else f"{value // 1000}kW"
            d.text(font, d.width - d.text_width(font, text), y + 7, color, text)
        # Animated dot in the gap between house and grid icons shows the direction
        if grid:
            step = self.flow_phase % 3
            d.set_pixel(3, 19 + step if exporting else 21 - step, *self.flow_color)


if __name__ == "__main__":
    run(PowerFlow)
