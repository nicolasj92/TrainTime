#!/usr/bin/env python3
"""
Utilities for LED Matrix Display
Contains Icon classes and Display class for rendering various modes:
- Christmas display with snow animation
- Power flow display with Home Assistant integration
"""

import time
import numpy as np
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

# All settings live in display_control/.env (see .env.example)
load_dotenv(Path(__file__).resolve().parent / '.env')

color_blue = [48, 118, 179]
color_black = [0, 0, 0]
color_yellow = [255, 255, 0]
color_orange = [214, 130, 53]
color_red = [255, 0, 0]

# Fonts are loaded after rgbmatrix drops root privileges to user 'daemon', which can't
# read /home/pi, so install.sh copies fonts/ here.
font_dir = os.getenv('FONT_DIR', '/usr/share/fonts/bdf')


class Icon(object):
    def __init__(self, canvas, pos_x, pos_y):
        self.canvas = canvas
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
                self.canvas.SetPixel(
                    x + self.pos_x, y + self.pos_y, *self.content[x, y]
                )


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


class IconError(Icon):
    def define_icon(self):
        self.content[1:7, 1:7] = color_red


class IconSun(Icon):
    def define_icon(self):
        # Center circle of the sun (3x3)
        circle_center = 3.5
        radius = 2.0  # Smaller circle
        for x in range(1, 7):  # Expanded range for bigger circle
            for y in range(1, 7):
                if (x-circle_center)**2 + (y-circle_center)**2 <= radius**2:  # Circle equation
                    self.content[x, y] = [255, 165, 0]  # Orange

        # Dot rays around the circle
        ray_positions = [
            (3, 0), (3, 7),  # Top and bottom
            (0, 3), (7, 3),  # Left and right
            (1, 1), (6, 1),  # Top corners
            (1, 6), (6, 6)   # Bottom corners
        ]
        for x, y in ray_positions:
            self.content[x, y] = [255, 165, 0]  # Orange dots


class IconHouse(Icon):
    def define_icon(self):
        # Roof (triangle)
        self.content[3, 1] = [100, 149, 237]  # Top point
        self.content[2, 2] = self.content[4, 2] = [100, 149, 237]  # Mid points
        self.content[1, 3] = self.content[5, 3] = [100, 149, 237]  # Bottom points
        
        # House body (rectangle)
        for x in range(2, 5):
            for y in range(4, 7):
                self.content[x, y] = [100, 149, 237]


class IconGrid(Icon):
    def define_icon(self):
        # Power line tower (simpler, cleaner design)
        # Base
        self.content[2, 6] = [100, 149, 237]
        self.content[3, 6] = [100, 149, 237]
        self.content[4, 6] = [100, 149, 237]
        # Left leg
        self.content[2, 5] = [100, 149, 237]
        self.content[3, 4] = [100, 149, 237]
        # Right leg
        self.content[4, 5] = [100, 149, 237]
        self.content[3, 4] = [100, 149, 237]
        # Top crossbar
        self.content[1, 3] = [100, 149, 237]
        self.content[2, 3] = [100, 149, 237]
        self.content[3, 3] = [100, 149, 237]
        self.content[4, 3] = [100, 149, 237]
        self.content[5, 3] = [100, 149, 237]
        # Top point
        self.content[3, 2] = [100, 149, 237]


class IconChristmasTree(Icon):
    def define_icon(self):
        # Increase tree size - make it 12x16 pixels instead of 8x8
        self.width = 12
        self.height = 16
        self.content = np.zeros((self.width, self.height, 3))

        # Star on top (yellow/gold) - make it bigger
        self.content[5, 0] = [255, 215, 0]
        self.content[6, 0] = [255, 215, 0]

        # Tree sections - build from top to bottom
        # Top section
        self.content[5, 1] = [0, 128, 0]
        self.content[6, 1] = [0, 128, 0]

        # Layer 2
        self.content[4, 2] = [0, 128, 0]
        self.content[5, 2] = [0, 150, 0]
        self.content[6, 2] = [0, 150, 0]
        self.content[7, 2] = [0, 128, 0]

        # Layer 3
        self.content[3, 3] = [0, 128, 0]
        self.content[4, 3] = [0, 150, 0]
        self.content[5, 3] = [0, 150, 0]
        self.content[6, 3] = [0, 150, 0]
        self.content[7, 3] = [0, 150, 0]
        self.content[8, 3] = [0, 128, 0]

        # Layer 4
        self.content[2, 4] = [0, 128, 0]
        self.content[3, 4] = [0, 150, 0]
        self.content[4, 4] = [0, 150, 0]
        self.content[5, 4] = [0, 150, 0]
        self.content[6, 4] = [0, 150, 0]
        self.content[7, 4] = [0, 150, 0]
        self.content[8, 4] = [0, 150, 0]
        self.content[9, 4] = [0, 128, 0]

        # Middle section starts (narrower)
        self.content[4, 5] = [0, 128, 0]
        self.content[5, 5] = [0, 150, 0]
        self.content[6, 5] = [0, 150, 0]
        self.content[7, 5] = [0, 128, 0]

        # Layer 6
        self.content[3, 6] = [0, 128, 0]
        self.content[4, 6] = [0, 150, 0]
        self.content[5, 6] = [0, 150, 0]
        self.content[6, 6] = [0, 150, 0]
        self.content[7, 6] = [0, 150, 0]
        self.content[8, 6] = [0, 128, 0]

        # Layer 7
        self.content[2, 7] = [0, 128, 0]
        self.content[3, 7] = [0, 150, 0]
        self.content[4, 7] = [0, 150, 0]
        self.content[5, 7] = [0, 150, 0]
        self.content[6, 7] = [0, 150, 0]
        self.content[7, 7] = [0, 150, 0]
        self.content[8, 7] = [0, 150, 0]
        self.content[9, 7] = [0, 128, 0]

        # Bottom section (widest)
        self.content[1, 8] = [0, 128, 0]
        self.content[2, 8] = [0, 150, 0]
        self.content[3, 8] = [0, 150, 0]
        self.content[4, 8] = [0, 150, 0]
        self.content[5, 8] = [0, 150, 0]
        self.content[6, 8] = [0, 150, 0]
        self.content[7, 8] = [0, 150, 0]
        self.content[8, 8] = [0, 150, 0]
        self.content[9, 8] = [0, 150, 0]
        self.content[10, 8] = [0, 128, 0]

        # Layer 9
        self.content[2, 9] = [0, 128, 0]
        self.content[3, 9] = [0, 150, 0]
        self.content[4, 9] = [0, 150, 0]
        self.content[5, 9] = [0, 150, 0]
        self.content[6, 9] = [0, 150, 0]
        self.content[7, 9] = [0, 150, 0]
        self.content[8, 9] = [0, 150, 0]
        self.content[9, 9] = [0, 128, 0]

        # Layer 10
        self.content[3, 10] = [0, 128, 0]
        self.content[4, 10] = [0, 150, 0]
        self.content[5, 10] = [0, 150, 0]
        self.content[6, 10] = [0, 150, 0]
        self.content[7, 10] = [0, 150, 0]
        self.content[8, 10] = [0, 128, 0]

        # Trunk (brown) - make it taller and wider
        self.content[4, 11] = [101, 67, 33]
        self.content[5, 11] = [101, 67, 33]
        self.content[6, 11] = [101, 67, 33]
        self.content[7, 11] = [101, 67, 33]

        self.content[4, 12] = [101, 67, 33]
        self.content[5, 12] = [101, 67, 33]
        self.content[6, 12] = [101, 67, 33]
        self.content[7, 12] = [101, 67, 33]

        self.content[4, 13] = [101, 67, 33]
        self.content[5, 13] = [101, 67, 33]
        self.content[6, 13] = [101, 67, 33]
        self.content[7, 13] = [101, 67, 33]


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


class Display:
    def __init__(self, interval=0.05):
        options = RGBMatrixOptions()
        options.chain_length = 2
        options.parallel = 2
        options.gpio_slowdown = int(os.getenv('LED_GPIO_SLOWDOWN') or default_gpio_slowdown())
        print(f"RGBMatrix gpio_slowdown: {options.gpio_slowdown}", flush=True)
        print(f"RGBMatrix brightness (options): {options.brightness}", flush=True)
        self.matrix = RGBMatrix(options=options)
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()

        self.font_small = graphics.Font()
        self.font_small.LoadFont(os.path.join(font_dir, "4x6.bdf"))
        self.font_large = graphics.Font()
        self.font_large.LoadFont(os.path.join(font_dir, "5x7.bdf"))
        self.textColor = graphics.Color(255, 255, 255)

        self.interval = interval
        self.flow_phase = 0
        self.flow_tick = 0

    def print_error(self, error_message):
        self.offscreen_canvas.Clear()
        time_str = datetime.now().strftime("%H:%M")

        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 20, 32 + 6, self.textColor, time_str
        )
        icon_error = IconError(self.offscreen_canvas, 28, 32 + 10)
        icon_error.draw()
        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 0, 32 + 24, self.textColor, error_message
        )

        time.sleep(self.interval)
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)

    def print_text(self, text):
        pass

    def print_word_clock(self):
        pass

    def print_large_clock(self):
        pass

    def print_datetime(self):
        pass

    def print_connections(self, route_information):
        self.offscreen_canvas.Clear()
        time_str = datetime.now().strftime("%H:%M")

        for i in range(2):
            for j, connection in enumerate(route_information[0][2][:3]):
                if connection.vehicle_type == "Bus":
                    icon_bus = IconBus(self.offscreen_canvas, i * 32, 32 + j * 8 + 8)
                    icon_bus.draw()
                elif connection.vehicle_type == "Tram":
                    icon_tram = IconTram(self.offscreen_canvas, i * 32, 32 + j * 8 + 8)
                    icon_tram.draw()

                text = "Party"
                if len(text) > 4:
                    use_font = self.font_small
                    pos = 32 + j * 8 + 14
                else:
                    use_font = self.font_large
                    pos = 32 + j * 8 + 15

                graphics.DrawText(
                    self.offscreen_canvas,
                    use_font,
                    i * 32 + 9,
                    pos,
                    self.textColor,
                    text,
                )

        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 20, 32 + 6, self.textColor, time_str
        )
        graphics.DrawText(
            self.offscreen_canvas, self.font_small, 0, 32 + 6, self.textColor, "HBF"
        )
        graphics.DrawText(
            self.offscreen_canvas, self.font_small, 50, 32 + 6, self.textColor, "LiWi"
        )

        time.sleep(self.interval)
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)

    def print_power_flow(self, solar_power, home_power, grid_power):
        """
        Display power flow information with simple lines and directional arrows
        solar_power: Current solar production in watts
        home_power: Current home consumption in watts
        grid_power: Current grid power (positive for consumption, negative for feed-in)
        """
        # Calculate power flow directions (do this once outside the loop)
        solar_to_home = min(solar_power, home_power)
        solar_to_grid = max(0, solar_power - home_power)
        grid_to_home = max(0, home_power - solar_power)

        self.offscreen_canvas.Clear()

        # Define colors - using blue/grey theme
        base_color = (60, 100, 160)  # Darker blue/grey for base lines
        text_color = graphics.Color(255, 255, 255)  # White for text

        # Define positions for the components
        grid_x, grid_y = 12, 32 + 18
        home_x, home_y = 52, 32 + 18

        def get_line_points(x0, y0, x1, y1):
            dx = abs(x1 - x0)
            dy = -abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx + dy
            points = []
            while True:
                points.append((x0, y0))
                if x0 == x1 and y0 == y1:
                    break
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x0 += sx
                if e2 <= dx:
                    err += dx
                    y0 += sy
            return points

        def draw_line(points, color):
            for px, py in points:
                self.offscreen_canvas.SetPixel(px, py, *color)

        def draw_flow_dots(points, phase, color):
            if not points:
                return
            spacing = 6
            for offset in range(0, len(points), spacing):
                idx = (offset + phase) % len(points)
                px, py = points[idx]
                self.offscreen_canvas.SetPixel(px, py, *color)

        def draw_arrow_tip(x, y, direction, color):
            if direction == "down":
                points = [(x, y), (x - 1, y - 1), (x + 1, y - 1)]
            elif direction == "up":
                points = [(x, y), (x - 1, y + 1), (x + 1, y + 1)]
            elif direction == "left":
                points = [(x, y), (x + 1, y - 1), (x + 1, y + 1)]
            else:
                points = [(x, y), (x - 1, y - 1), (x - 1, y + 1)]
            for px, py in points:
                self.offscreen_canvas.SetPixel(px, py, *color)

        # Draw time
        time_str = datetime.now().strftime("%H:%M")
        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 0, 32 + 6, text_color, time_str
        )

        # Draw icons and labels
        solar_text = f"{solar_power}W"
        solar_width = len(solar_text) * 6
        solar_text_x = 64 - solar_width
        sun_icon = IconSun(self.offscreen_canvas, solar_text_x - 12, 32)
        sun_icon.draw()
        graphics.DrawText(
            self.offscreen_canvas, self.font_large, solar_text_x, 32 + 6, text_color, solar_text
        )

        house_icon = IconHouse(self.offscreen_canvas, home_x + 2, 32 + 14)
        house_icon.draw()

        grid_icon = IconGrid(self.offscreen_canvas, grid_x - 8, 32 + 14)
        grid_icon.draw()

        home_text = f"{home_power}W"
        home_width = len(home_text) * 6
        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 64 - home_width, home_y + 12, text_color, home_text
        )

        grid_text = f"{abs(grid_power)}W"
        graphics.DrawText(
            self.offscreen_canvas, self.font_large, grid_x - 8, grid_y + 12, text_color, grid_text
        )

        # Anchor points for lines
        solar_anchor = (solar_text_x - 8, 32 + 4)
        home_anchor = (home_x + 6, 32 + 18)
        grid_anchor = (grid_x - 4, 32 + 18)

        # Draw simple flow lines with arrowheads
        flow_color = (110, 170, 255)
        if solar_to_home > 0:
            points = get_line_points(solar_anchor[0], solar_anchor[1], home_anchor[0], home_anchor[1])
            draw_line(points, base_color)
            draw_flow_dots(points, self.flow_phase, flow_color)
            draw_arrow_tip(home_anchor[0], home_anchor[1], "down", base_color)

        if solar_to_grid > 0:
            points = get_line_points(solar_anchor[0], solar_anchor[1], grid_anchor[0], grid_anchor[1])
            draw_line(points, base_color)
            draw_flow_dots(points, self.flow_phase, flow_color)
            draw_arrow_tip(grid_anchor[0], grid_anchor[1], "left", base_color)

        if grid_to_home > 0:
            points = get_line_points(grid_anchor[0], grid_anchor[1], home_anchor[0], home_anchor[1])
            draw_line(points, base_color)
            draw_flow_dots(points, self.flow_phase, flow_color)
            draw_arrow_tip(home_anchor[0], home_anchor[1], "right", base_color)

        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
        self.flow_tick = (self.flow_tick + 1) % 1000
        if self.flow_tick % 3 == 0:
            self.flow_phase = (self.flow_phase + 1) % 6
        time.sleep(self.interval)

    def print_christmas(
        self,
        ornament_positions=None,
        blink_state=0,
        snow_accumulation=None,
        plow_position=None,
        plow_direction=1,
        houses=None,
    ):
        """
        Display a simple scene with just time and falling snow
        snow_accumulation: dict mapping x-coordinate to height of accumulated snow
        plow_position: x-coordinate of snowplow, or None if not active
        """
        self.offscreen_canvas.Clear()

        # Draw time - using larger font
        time_str = datetime.now().strftime("%H:%M")
        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 20, 32 + 6, self.textColor, time_str
        )

        # Draw accumulated snow at the bottom
        if snow_accumulation:
            snow_color = (170, 200, 255)  # Blue-tinted snow
            for x, height in snow_accumulation.items():
                for y in range(height):
                    bottom_y = 63 - y  # Draw from bottom up
                    self.offscreen_canvas.SetPixel(x, bottom_y, *snow_color)

        # Draw small background houses with flickering windows and roof snow
        if houses:
            house_color = (30, 30, 40)
            roof_color = (55, 55, 70)
            roof_ridge_color = (75, 75, 95)
            window_color_base = (255, 210, 70)
            roof_snow_color = (190, 210, 255)
            for house in houses:
                x = house["x"]
                y = house["y"]
                w = house["w"]
                h = house["h"]
                roof_h = house.get("roof_h", 3)
                roof_base_y = y - h
                peak_x = x + w // 2
                roof_overhang = 2
                # House body
                for dx in range(w):
                    for dy in range(h):
                        px = x + dx
                        py = y - dy
                        if 0 <= px < 64 and 0 <= py < 64:
                            self.offscreen_canvas.SetPixel(px, py, *house_color)
                # Roof (shallower slope ~120 degrees) slightly larger than base
                for dx in range(-roof_overhang, w + roof_overhang):
                    px = x + dx
                    slope = roof_h - (abs(px - peak_x) + 1) // 2
                    if slope < 0:
                        continue
                    roof_y = roof_base_y - slope
                    for py in range(roof_base_y, roof_y - 1, -1):
                        if 0 <= px < 64 and 0 <= py < 64:
                            self.offscreen_canvas.SetPixel(px, py, *roof_color)
                    if 0 <= px < 64 and 0 <= roof_y < 64:
                        self.offscreen_canvas.SetPixel(px, roof_y, *roof_ridge_color)
                # Small chimney
                chimney_x = x + w - 2
                chimney_top = roof_base_y - roof_h + 1
                for dy in range(3):
                    px = chimney_x
                    py = chimney_top - dy
                    if 0 <= px < 64 and 0 <= py < 64:
                        self.offscreen_canvas.SetPixel(px, py, *roof_ridge_color)
                chimney_snow = house.get("chimney_snow", 0)
                chimney_cap_y = chimney_top - 3
                for dy in range(chimney_snow):
                    py = chimney_cap_y - dy
                    if 0 <= chimney_x < 64 and 0 <= py < 64:
                        self.offscreen_canvas.SetPixel(chimney_x, py, *roof_snow_color)
                # Roof overhang: 1px diagonal tails
                for px, py in ((x - 1, roof_base_y + 1), (x + w, roof_base_y + 1)):
                    if 0 <= px < 64 and 0 <= py < 64:
                        self.offscreen_canvas.SetPixel(px, py, *roof_color)
                # Roof snow per pixel
                roof_snow = house.get("roof_snow", [])
                for dx in range(-roof_overhang, w + roof_overhang):
                    idx = dx + roof_overhang
                    if idx < 0 or idx >= len(roof_snow):
                        continue
                    px = x + dx
                    slope = roof_h - (abs(px - peak_x) + 1) // 2
                    if slope < 0:
                        continue
                    roof_y = roof_base_y - slope - 1
                    for dy in range(roof_snow[idx]):
                        py = roof_y - dy
                        if 0 <= px < 64 and 0 <= py < 64:
                            self.offscreen_canvas.SetPixel(px, py, *roof_snow_color)
                # Windows
                window_level = house.get("window_level", 90)
                window_color = (
                    min(255, int(window_color_base[0] * window_level / 160)),
                    min(255, int(window_color_base[1] * window_level / 160)),
                    min(255, int(window_color_base[2] * window_level / 160)),
                )
                for window in house.get("windows", []):
                    if len(window) == 2:
                        wx, wy = window
                        ww, wh = 1, 1
                    else:
                        wx, wy, ww, wh = window
                    for dx in range(ww):
                        for dy in range(wh):
                            px = x + wx + dx
                            py = y - wy - dy
                            if 0 <= px < 64 and 0 <= py < 64:
                                self.offscreen_canvas.SetPixel(px, py, *window_color)

        # Draw snowplow if active
        if plow_position is not None:
            # Snowplow with angled blade at front (right side)
            plow_color = (255, 200, 0)  # Yellow body
            plow_dark = (200, 150, 0)
            window_color = (180, 220, 255)
            blade_color = (120, 120, 120)  # Gray blade
            dark_gray = (80, 80, 80)  # Darker gray for details
            tread_color = (40, 40, 40)

            body_width = 10
            body_height = 5
            body_top = 59

            # Plow body
            for dx in range(body_width):
                px = plow_position + dx
                if 0 <= px < 64:
                    for dy in range(body_height):
                        py = body_top + dy
                        color = plow_color
                        if dy == body_height - 1:
                            color = plow_dark
                        self.offscreen_canvas.SetPixel(px, py, *color)

            # Window
            window_offset = 6 if plow_direction == 1 else 2
            for dx in range(2):
                px = plow_position + window_offset + dx
                for dy in range(2):
                    py = body_top + 1 + dy
                    if 0 <= px < 64:
                        self.offscreen_canvas.SetPixel(px, py, *window_color)

            # Treads (alternate pixels on bottom row)
            if blink_state % 2 == 0:
                tread_offsets = [1, 3, 5, 7, 9]
            else:
                tread_offsets = [0, 2, 4, 6, 8]
            for dx in tread_offsets:
                px = plow_position + dx
                py = body_top + body_height - 1
                if 0 <= px < 64:
                    self.offscreen_canvas.SetPixel(px, py, *tread_color)

            # Beacon
            if blink_state % 8 < 4:
                beacon_x = plow_position + (7 if plow_direction == 1 else 2)
                beacon_y = body_top - 1
                if 0 <= beacon_x < 64 and 0 <= beacon_y < 64:
                    self.offscreen_canvas.SetPixel(beacon_x, beacon_y, 255, 180, 0)

            # Angled blade at the front based on direction
            if plow_direction == 1:
                blade_base = plow_position + body_width
                blade_pixels = [
                    (blade_base, 63, blade_color),
                    (blade_base + 1, 63, blade_color),
                    (blade_base + 2, 63, dark_gray),
                    (blade_base, 62, blade_color),
                    (blade_base + 1, 62, blade_color),
                    (blade_base + 2, 62, dark_gray),
                    (blade_base + 1, 61, blade_color),
                    (blade_base + 2, 61, blade_color),
                    (blade_base + 2, 60, dark_gray),
                ]
            else:
                blade_base = plow_position - 1
                blade_pixels = [
                    (blade_base, 63, blade_color),
                    (blade_base - 1, 63, blade_color),
                    (blade_base - 2, 63, dark_gray),
                    (blade_base, 62, blade_color),
                    (blade_base - 1, 62, blade_color),
                    (blade_base - 2, 62, dark_gray),
                    (blade_base - 1, 61, blade_color),
                    (blade_base - 2, 61, blade_color),
                    (blade_base - 2, 60, dark_gray),
                ]
            for px, py, color in blade_pixels:
                if 0 <= px < 64 and 0 <= py < 64:
                    self.offscreen_canvas.SetPixel(px, py, *color)

        # Return the canvas without swapping (caller will handle animation)
        return self.offscreen_canvas

if __name__ == "__main__":
    display = Display(interval=0.02)  # Faster interval for smoother animation
    
    try:
        while True:
            
            # Scenario 2: Home needs more than solar produces
            for _ in range(2):
                display.print_power_flow(
                    solar_power=1000,  # Solar producing 1kW
                    home_power=1500,   # Home using 1.5kW
                    grid_power=500     # Drawing 500W from grid
                )
            
            # Scenario 1: Solar producing more than home needs
            for _ in range(2):  # Show each scenario for longer (25 * 2 seconds)
                display.print_power_flow(
                    solar_power=2000,  # Solar producing 2kW
                    home_power=1500,   # Home using 1.5kW
                    grid_power=-500    # Feeding 500W to grid
                )

            # Scenario 3: No solar, all from grid
            for _ in range(2):
                display.print_power_flow(
                    solar_power=0,     # No solar production
                    home_power=2000,   # Home using 2kW
                    grid_power=2000    # All power from grid
                )
            
    except KeyboardInterrupt:
        print("Stopping power flow display...")
