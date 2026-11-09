#!/usr/bin/env python3
"""
Christmas mode: clock with falling snow that piles up on the ground and on house roofs,
melts slowly, and gets cleared by a passing snowplow. Works on 64x32 and 32x32.
"""

import math
import random

from utils import Display, run

SNOW_COLOR = (170, 200, 255)
MAX_GROUND_SNOW = 10
ROOF_OVERHANG = 2
PLOW_WIDTH = 10
PLOW_BLADE = 3


def plow_interval():
    return random.randint(1000, 2000)  # frames; 50-100 s at 20 fps


class Snowflake:
    """A falling snowflake. Starts above the panel; y may be negative (not drawn)."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.x = random.randint(0, width - 1)
        # Spawn up to one panel-height above the top so flakes arrive spread out
        self.y = random.randint(-height, 0) - height
        self.speed = random.choice([0.08, 0.12, 0.16])
        self.drift = random.choice([-0.15, 0, 0.15])
        self.y_float = float(self.y)

    def respawn(self):
        self.y = random.randint(-10, 0) - self.height
        self.y_float = float(self.y)
        self.x = random.randint(0, self.width - 1)

    def fall(self):
        self.y_float += self.speed
        self.y = math.floor(self.y_float)
        if random.random() < 0.2:
            self.x += int(self.drift)
            self.x = max(0, min(self.width - 1, self.x))
        if self.y >= self.height:
            self.respawn()

    def is_visible(self):
        return -self.height <= self.y < self.height


def make_house(x, ground_y, w, roof_h, windows, window_level, target_level):
    return {
        "x": x, "y": ground_y, "w": w, "h": 6, "roof_h": roof_h, "windows": windows,
        "roof_snow": [0] * (w + ROOF_OVERHANG * 2), "chimney_snow": 0,
        "window_level": window_level, "target_level": target_level,
    }


class Christmas:
    fps = 20

    def __init__(self, display: Display):
        self.d = display
        W, H = display.width, display.height
        self.snowflakes = [Snowflake(W, H) for _ in range(30 if display.wide else 15)]
        self.ground = {x: 0 for x in range(W)}
        self.plow_active = False
        self.plow_position = -(PLOW_WIDTH + PLOW_BLADE)
        self.plow_direction = 1
        self.frames_until_plow = plow_interval()
        self.blink = 0
        if display.wide:
            self.houses = [
                make_house(8, H - 11, 9, 2, [(1, 2, 2, 2), (5, 2, 2, 2)], 80, 90),
                make_house(44, H - 7, 10, 3, [(1, 2, 2, 2), (6, 2, 2, 2)], 90, 110),
            ]
        else:
            self.houses = [make_house(W - 13, H - 7, 9, 2, [(1, 2, 2, 2), (5, 2, 2, 2)], 90, 110)]

    # --- simulation ---

    def _update_plow(self):
        W = self.d.width
        if not self.plow_active:
            self.frames_until_plow -= 1
            if self.frames_until_plow <= 0:
                self.plow_active = True
                self.plow_direction = random.choice([1, -1])
                if self.plow_direction == 1:
                    self.plow_position = -(PLOW_WIDTH + PLOW_BLADE)
                else:
                    self.plow_position = W + PLOW_BLADE

        if self.plow_active and self.blink % 2 == 0:  # move every other frame
            self.plow_position += self.plow_direction
            if self.plow_direction == 1:
                clear = range(self.plow_position, self.plow_position + PLOW_WIDTH + PLOW_BLADE)
            else:
                clear = range(self.plow_position - PLOW_BLADE, self.plow_position + PLOW_WIDTH)
            for px in clear:
                if 0 <= px < W:
                    self.ground[px] = 0
            if (self.plow_direction == 1 and self.plow_position > W) or \
               (self.plow_direction == -1 and self.plow_position + PLOW_WIDTH < 0):
                self.plow_active = False
                self.frames_until_plow = plow_interval()

    def _update_windows(self):
        for house in self.houses:
            if self.blink % 8 == 0:
                house["target_level"] = random.randint(50, 170)
            if house["window_level"] < house["target_level"]:
                house["window_level"] += 2
            elif house["window_level"] > house["target_level"]:
                house["window_level"] -= 2
            house["window_level"] = max(40, min(190, house["window_level"] + random.randint(-3, 3)))

    def _land_on_roof(self, flake):
        """Returns True if the flake landed on a roof or chimney (and respawns it)."""
        for house in self.houses:
            if not (house["x"] - ROOF_OVERHANG <= flake.x < house["x"] + house["w"] + ROOF_OVERHANG):
                continue
            idx = flake.x - house["x"] + ROOF_OVERHANG
            if idx < 0 or idx >= len(house["roof_snow"]):
                continue
            roof_base_y = house["y"] - house["h"]
            peak_x = house["x"] + house["w"] // 2
            slope = house["roof_h"] - (abs(flake.x - peak_x) + 1) // 2
            if slope < 0:
                continue
            roof_y = roof_base_y - slope - 1
            chimney_x = house["x"] + house["w"] - 2
            chimney_top = roof_base_y - house["roof_h"] + 1 - 3
            if flake.x == chimney_x and house["chimney_snow"] < 2 and \
               chimney_top <= flake.y <= chimney_top + 1:
                house["chimney_snow"] += 1
                flake.respawn()
                return True
            if roof_y - house["roof_snow"][idx] <= flake.y <= roof_y:
                if house["roof_snow"][idx] < 2:
                    house["roof_snow"][idx] += 1
                flake.respawn()
                return True
        return False

    def _update_and_draw_snow(self, clock_x, clock_w):
        d, H = self.d, self.d.height
        bottom = H - 1
        for flake in self.snowflakes:
            if flake.is_visible():
                if flake.y >= bottom - self.ground.get(flake.x, 0):
                    if self.ground[flake.x] < MAX_GROUND_SNOW:
                        self.ground[flake.x] += 1
                    flake.respawn()
                elif self._land_on_roof(flake):
                    flake.fall()
                    continue
                elif not (clock_x - 2 <= flake.x <= clock_x + clock_w and 0 <= flake.y <= 7):
                    # Sub-pixel smoothing: split brightness between this pixel and the next
                    fraction = flake.y_float - flake.y
                    main = max(0, min(255, int(255 * (1.0 - fraction * 0.5))))
                    d.set_pixel(flake.x, flake.y, main, main, main)
                    if flake.y + 1 < H:
                        nxt = max(0, min(255, int(255 * fraction * 0.5)))
                        if nxt > 0:
                            d.set_pixel(flake.x, flake.y + 1, nxt, nxt, nxt)
            flake.fall()

    def _melt(self):
        if self.blink % 100 == 0:
            for _ in range(2):
                x = random.randint(0, self.d.width - 1)
                if self.ground[x] > 0:
                    self.ground[x] -= 1
        if self.blink % 200 == 0:
            for house in self.houses:
                melt_idx = random.randint(0, len(house["roof_snow"]) - 1)
                if house["roof_snow"][melt_idx] > 0:
                    house["roof_snow"][melt_idx] -= 1
                if house["chimney_snow"] > 0 and random.random() < 0.5:
                    house["chimney_snow"] -= 1

    def frame(self):
        self._update_plow()
        d = self.d
        d.clear()
        clock_x, clock_w = d.clock()
        self._draw_ground()
        for house in self.houses:
            self._draw_house(house)
        if self.plow_active:
            self._draw_plow()
        self._update_windows()
        self._update_and_draw_snow(clock_x, clock_w)
        self.blink += 1
        self._melt()

    # --- drawing ---

    def _draw_ground(self):
        bottom = self.d.height - 1
        for x, height in self.ground.items():
            for y in range(height):
                self.d.set_pixel(x, bottom - y, *SNOW_COLOR)

    def _draw_house(self, house):
        px_ = self.d.set_pixel
        house_color = (30, 30, 40)
        roof_color = (55, 55, 70)
        ridge_color = (75, 75, 95)
        roof_snow_color = (190, 210, 255)
        x, y, w, h, roof_h = house["x"], house["y"], house["w"], house["h"], house["roof_h"]
        roof_base_y = y - h
        peak_x = x + w // 2

        for dx in range(w):
            for dy in range(h):
                px_(x + dx, y - dy, *house_color)
        for dx in range(-ROOF_OVERHANG, w + ROOF_OVERHANG):
            px = x + dx
            slope = roof_h - (abs(px - peak_x) + 1) // 2
            if slope < 0:
                continue
            roof_y = roof_base_y - slope
            for py in range(roof_base_y, roof_y - 1, -1):
                px_(px, py, *roof_color)
            px_(px, roof_y, *ridge_color)
        chimney_x = x + w - 2
        chimney_top = roof_base_y - roof_h + 1
        for dy in range(3):
            px_(chimney_x, chimney_top - dy, *ridge_color)
        for dy in range(house["chimney_snow"]):
            px_(chimney_x, chimney_top - 3 - dy, *roof_snow_color)
        for px, py in ((x - 1, roof_base_y + 1), (x + w, roof_base_y + 1)):
            px_(px, py, *roof_color)
        for dx in range(-ROOF_OVERHANG, w + ROOF_OVERHANG):
            px = x + dx
            slope = roof_h - (abs(px - peak_x) + 1) // 2
            if slope < 0:
                continue
            roof_y = roof_base_y - slope - 1
            for dy in range(house["roof_snow"][dx + ROOF_OVERHANG]):
                px_(px, roof_y - dy, *roof_snow_color)

        level = house["window_level"]
        window_color = tuple(min(255, int(c * level / 160)) for c in (255, 210, 70))
        for wx, wy, ww, wh in house["windows"]:
            for dx in range(ww):
                for dy in range(wh):
                    px_(x + wx + dx, y - wy - dy, *window_color)

    def _draw_plow(self):
        px_ = self.d.set_pixel
        pos, direction, blink = self.plow_position, self.plow_direction, self.blink
        bottom = self.d.height - 1
        body_w, body_h = PLOW_WIDTH, 5
        body_top = bottom - 4
        yellow, yellow_dark = (255, 200, 0), (200, 150, 0)
        glass, blade, dark, tread = (180, 220, 255), (120, 120, 120), (80, 80, 80), (40, 40, 40)

        for dx in range(body_w):
            for dy in range(body_h):
                px_(pos + dx, body_top + dy, *(yellow_dark if dy == body_h - 1 else yellow))
        window_offset = 6 if direction == 1 else 2
        for dx in range(2):
            for dy in range(2):
                px_(pos + window_offset + dx, body_top + 1 + dy, *glass)
        for dx in ([1, 3, 5, 7, 9] if blink % 2 == 0 else [0, 2, 4, 6, 8]):
            px_(pos + dx, bottom, *tread)
        if blink % 8 < 4:
            px_(pos + (7 if direction == 1 else 2), body_top - 1, 255, 180, 0)

        s = 1 if direction == 1 else -1
        base = pos + body_w if direction == 1 else pos - 1
        for dx, dy, color in [(0, 0, blade), (1, 0, blade), (2, 0, dark),
                              (0, 1, blade), (1, 1, blade), (2, 1, dark),
                              (1, 2, blade), (2, 2, blade), (2, 3, dark)]:
            px_(base + s * dx, bottom - dy, *color)


if __name__ == "__main__":
    run(Christmas)
