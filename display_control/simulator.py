#!/usr/bin/env python3
"""
LED Matrix Display Simulator
Generates images and GIFs to preview display modes without hardware
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
import random


class MockCanvas:
    """Mock canvas that simulates the LED matrix canvas"""
    def __init__(self, width=64, height=64):
        self.width = width
        self.height = height
        # Store pixels as RGB array
        self.pixels = np.zeros((height, width, 3), dtype=np.uint8)

    def SetPixel(self, x, y, r, g, b):
        """Set a pixel color"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y, x] = [r, g, b]

    def Clear(self):
        """Clear all pixels"""
        self.pixels.fill(0)

    def get_image(self, scale=10):
        """
        Convert pixel array to PIL Image with scaling
        scale: Factor to scale up the image (10 = 10x larger)
        """
        # Create upscaled image
        img = Image.new('RGB', (self.width * scale, self.height * scale))
        pixels = img.load()

        for y in range(self.height):
            for x in range(self.width):
                color = tuple(self.pixels[y, x])
                # Fill scaled block
                for dy in range(scale):
                    for dx in range(scale):
                        pixels[x * scale + dx, y * scale + dy] = color

        return img


class BDFFont:
    """BDF Font parser and renderer for realistic text rendering"""
    def __init__(self):
        self.char_width = 5
        self.char_height = 7
        self.glyphs = {}
        self.loaded = False

    def LoadFont(self, path):
        """Load BDF font file"""
        try:
            with open(path, 'r', encoding='latin-1') as f:
                self._parse_bdf(f)
            self.loaded = True
            return True
        except Exception as e:
            print(f"Warning: Could not load font {path}: {e}")
            self.loaded = False
            return False

    def _parse_bdf(self, f):
        """Parse BDF font format"""
        current_char = None
        bitmap = []
        in_bitmap = False

        for line in f:
            line = line.strip()

            if line.startswith('FONTBOUNDINGBOX'):
                parts = line.split()
                self.char_width = int(parts[1])
                self.char_height = int(parts[2])

            elif line.startswith('ENCODING'):
                if current_char is not None and bitmap:
                    self.glyphs[current_char] = bitmap
                current_char = int(line.split()[1])
                bitmap = []
                in_bitmap = False

            elif line == 'BITMAP':
                in_bitmap = True

            elif line == 'ENDCHAR':
                if current_char is not None and bitmap:
                    self.glyphs[current_char] = bitmap
                in_bitmap = False

            elif in_bitmap and line:
                # Convert hex to binary bitmap
                bitmap.append(int(line, 16))

    def get_char_bitmap(self, char):
        """Get bitmap for a character"""
        if not self.loaded or ord(char) not in self.glyphs:
            return None
        return self.glyphs[ord(char)]


class MockGraphics:
    """Mock graphics module with BDF font rendering"""
    @staticmethod
    def Color(r, g, b):
        """Return color as tuple"""
        return (r, g, b)

    @staticmethod
    def DrawText(canvas, font, x, y, color, text):
        """Render text using BDF font if available"""
        if isinstance(color, tuple):
            r, g, b = color
        else:
            r, g, b = 255, 255, 255

        if not hasattr(font, 'loaded') or not font.loaded:
            # Fallback to simple rendering
            for i, char in enumerate(text):
                if char == ' ':
                    continue
                char_x = x + i * font.char_width
                for dx in range(font.char_width - 1):
                    for dy in range(font.char_height - 1):
                        px = char_x + dx
                        py = y - font.char_height + 2 + dy
                        if 0 <= px < canvas.width and 0 <= py < canvas.height:
                            if dx == 0 or dy == 0 or dx == font.char_width - 2:
                                canvas.SetPixel(px, py, r, g, b)
            return

        # Render using actual BDF font
        cursor_x = x
        for char in text:
            if char == ' ':
                cursor_x += font.char_width
                continue

            bitmap = font.get_char_bitmap(char)
            if bitmap is None:
                cursor_x += font.char_width
                continue

            # Draw the character bitmap
            for row_idx, row_data in enumerate(bitmap):
                py = y - font.char_height + row_idx + 1
                if py < 0 or py >= canvas.height:
                    continue

                # Convert row to binary and draw pixels
                for bit_idx in range(font.char_width):
                    if row_data & (1 << (font.char_width - 1 - bit_idx)):
                        px = cursor_x + bit_idx
                        if 0 <= px < canvas.width:
                            canvas.SetPixel(px, py, r, g, b)

            cursor_x += font.char_width


class DisplaySimulator:
    """Simulates the LED matrix display for preview purposes"""

    def __init__(self, width=64, height=64):
        self.width = width
        self.height = height
        self.canvas = MockCanvas(width, height)

    def _draw_icon_sun(self, x, y):
        sun_color = (255, 165, 0)
        circle = [
            (2, 1), (3, 1),
            (1, 2), (2, 2), (3, 2), (4, 2),
            (1, 3), (2, 3), (3, 3), (4, 3),
            (2, 4), (3, 4),
        ]
        rays = [(0, 2), (5, 2), (2, 0), (2, 5), (4, 0), (0, 4), (4, 5), (5, 4)]
        for dx, dy in circle + rays:
            self.canvas.SetPixel(x + dx, y + dy, *sun_color)

    def _draw_icon_house(self, x, y):
        house_color = (100, 149, 237)
        roof = [(2, 0), (1, 1), (3, 1), (0, 2), (4, 2)]
        for dx, dy in roof:
            self.canvas.SetPixel(x + dx, y + dy, *house_color)
        for dx in range(1, 4):
            for dy in range(3, 6):
                self.canvas.SetPixel(x + dx, y + dy, *house_color)

    def _draw_icon_grid(self, x, y):
        grid_color = (100, 149, 237)
        points = [
            (2, 0), (1, 1), (2, 1), (3, 1),
            (0, 2), (1, 2), (2, 2), (3, 2), (4, 2),
            (2, 3), (1, 4), (3, 4), (0, 5), (4, 5),
        ]
        for dx, dy in points:
            self.canvas.SetPixel(x + dx, y + dy, *grid_color)

    def render_power_flow_frame(self, solar_power, home_power, grid_power):
        """
        Render a single frame of the power flow display.
        Returns PIL Image.
        """
        from datetime import datetime

        graphics = MockGraphics()
        import os
        font_dir = os.path.join(os.path.dirname(__file__), 'fonts')

        font_large = BDFFont()
        font_large.LoadFont(os.path.join(font_dir, '5x7.bdf'))

        self.canvas.Clear()

        base_color = (60, 100, 160)
        text_color = (255, 255, 255)

        def draw_line(x0, y0, x1, y1, color):
            dx = abs(x1 - x0)
            dy = -abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx + dy
            while True:
                self.canvas.SetPixel(x0, y0, *color)
                if x0 == x1 and y0 == y1:
                    break
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x0 += sx
                if e2 <= dx:
                    err += dx
                    y0 += sy

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
                self.canvas.SetPixel(px, py, *color)

        # Time
        time_str = datetime.now().strftime("%H:%M")
        graphics.DrawText(self.canvas, font_large, 0, 32 + 6, text_color, time_str)

        grid_x, grid_y = 12, 32 + 18
        home_x, home_y = 52, 32 + 18

        solar_text = f"{solar_power}W"
        solar_text_x = 64 - len(solar_text) * 6
        self._draw_icon_sun(solar_text_x - 8, 32 + 1)
        graphics.DrawText(self.canvas, font_large, solar_text_x, 32 + 6, text_color, solar_text)

        self._draw_icon_house(home_x + 2, 32 + 14)
        self._draw_icon_grid(grid_x - 6, 32 + 14)

        home_text = f"{home_power}W"
        home_text_x = 64 - len(home_text) * 6
        graphics.DrawText(self.canvas, font_large, home_text_x, home_y + 12, text_color, home_text)

        grid_text = f"{abs(grid_power)}W"
        graphics.DrawText(self.canvas, font_large, grid_x - 8, grid_y + 12, text_color, grid_text)

        solar_to_home = min(solar_power, home_power)
        solar_to_grid = max(0, solar_power - home_power)
        grid_to_home = max(0, home_power - solar_power)

        solar_anchor = (solar_text_x - 6, 32 + 4)
        home_anchor = (home_x + 6, 32 + 18)
        grid_anchor = (grid_x - 4, 32 + 18)

        if solar_to_home > 0:
            draw_line(solar_anchor[0], solar_anchor[1], home_anchor[0], home_anchor[1], base_color)
            draw_arrow_tip(home_anchor[0], home_anchor[1], "down", base_color)

        if solar_to_grid > 0:
            draw_line(solar_anchor[0], solar_anchor[1], grid_anchor[0], grid_anchor[1], base_color)
            draw_arrow_tip(grid_anchor[0], grid_anchor[1], "left", base_color)

        if grid_to_home > 0:
            draw_line(grid_anchor[0], grid_anchor[1], home_anchor[0], home_anchor[1], base_color)
            draw_arrow_tip(home_anchor[0], home_anchor[1], "right", base_color)

        return self.canvas.get_image(scale=10)

    def generate_power_preview(self, output_path='power_preview.png'):
        img = self.render_power_flow_frame(
            solar_power=150,
            home_power=420,
            grid_power=270
        )
        img.save(output_path)
        print(f"✓ Saved power preview to {output_path}")
        return output_path

    def render_christmas_frame(self, blink_state=0, snowflakes=None):
        """
        Render a single frame of the Christmas display
        Returns PIL Image
        """
        from datetime import datetime

        # Mock the graphics module
        graphics = MockGraphics()

        # Create BDF fonts
        import os
        font_dir = os.path.join(os.path.dirname(__file__), 'fonts')

        font_small = BDFFont()
        font_small.LoadFont(os.path.join(font_dir, '4x6.bdf'))

        font_large = BDFFont()
        font_large.LoadFont(os.path.join(font_dir, '5x7.bdf'))

        # Clear canvas
        self.canvas.Clear()

        # Draw time
        time_str = datetime.now().strftime("%H:%M")
        textColor = (255, 255, 255)
        graphics.DrawText(
            self.canvas, font_large, 20, 32 + 6, textColor, time_str
        )

        # Draw accumulated snow at the bottom
        snow_color = (170, 200, 255)
        for x in range(self.width):
            height = 1 + (1 if x % 9 == 0 else 0)
            for y in range(height):
                bottom_y = self.height - 1 - y
                self.canvas.SetPixel(x, bottom_y, *snow_color)

        # Draw small background houses
        roof_overhang = 2
        houses = [
            {"x": 8, "y": 53, "w": 9, "h": 6, "roof_h": 2, "windows": [(1, 2, 2, 2), (5, 2, 2, 2)], "window_level": 90, "roof_snow": [0] * (9 + roof_overhang * 2)},
            {"x": 44, "y": 57, "w": 10, "h": 6, "roof_h": 3, "windows": [(1, 2, 2, 2), (6, 2, 2, 2)], "window_level": 110, "roof_snow": [0] * (10 + roof_overhang * 2)},
        ]
        house_color = (30, 30, 40)
        roof_color = (55, 55, 70)
        roof_ridge_color = (75, 75, 95)
        window_color_base = (255, 210, 70)
        for house in houses:
            x = house["x"]
            y = house["y"]
            w = house["w"]
            h = house["h"]
            roof_h = house["roof_h"]
            roof_base_y = y - h
            peak_x = x + w // 2
            roof_overhang = 2
            # House body
            for dx in range(w):
                for dy in range(h):
                    px = x + dx
                    py = y - dy
                    if 0 <= px < self.width and 0 <= py < self.height:
                        self.canvas.SetPixel(px, py, *house_color)
            # Roof (shallower slope ~120 degrees) slightly larger than base
            for dx in range(-roof_overhang, w + roof_overhang):
                px = x + dx
                slope = roof_h - (abs(px - peak_x) + 1) // 2
                if slope < 0:
                    continue
                roof_y = roof_base_y - slope
                for py in range(roof_base_y, roof_y - 1, -1):
                    if 0 <= px < self.width and 0 <= py < self.height:
                        self.canvas.SetPixel(px, py, *roof_color)
                if 0 <= px < self.width and 0 <= roof_y < self.height:
                    self.canvas.SetPixel(px, roof_y, *roof_ridge_color)
            # Small chimney
            chimney_x = x + w - 2
            chimney_top = roof_base_y - roof_h + 1
            for dy in range(3):
                px = chimney_x
                py = chimney_top - dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    self.canvas.SetPixel(px, py, *roof_ridge_color)
            # Roof overhang: 1px diagonal tails
            for px, py in ((x - 1, roof_base_y + 1), (x + w, roof_base_y + 1)):
                if 0 <= px < self.width and 0 <= py < self.height:
                    self.canvas.SetPixel(px, py, *roof_color)
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
                    if 0 <= px < self.width and 0 <= py < self.height:
                        self.canvas.SetPixel(px, py, *snow_color)
            # Windows
            window_level = house.get("window_level", 90)
            window_color = (
                min(255, int(window_color_base[0] * window_level / 160)),
                min(255, int(window_color_base[1] * window_level / 160)),
                min(255, int(window_color_base[2] * window_level / 160)),
            )
            for window in house.get("windows", []):
                wx, wy, ww, wh = window
                for dx in range(ww):
                    for dy in range(wh):
                        px = x + wx + dx
                        py = y - wy - dy
                        if 0 <= px < self.width and 0 <= py < self.height:
                            self.canvas.SetPixel(px, py, *window_color)

        # Draw snowflakes if provided
        if snowflakes:
            snow_color = (255, 255, 255)
            for flake in snowflakes:
                if 0 <= flake.y < self.height:
                    self.canvas.SetPixel(int(flake.x), int(flake.y), *snow_color)

        return self.canvas.get_image(scale=10)

    def generate_static_preview(self, output_path='christmas_preview.png', blink_state=5):
        """Generate a static preview image"""
        print(f"Generating static preview: {output_path}")

        # Create some snowflakes for the preview
        from christmas_display import Snowflake
        snowflakes = [Snowflake(width=64, height=64) for _ in range(30)]
        # Position them randomly on screen
        for flake in snowflakes:
            flake.y = random.randint(0, 63)

        img = self.render_christmas_frame(blink_state=blink_state, snowflakes=snowflakes)
        # Crop to visible 64x32 region (bottom half) for the real panel
        scale = 10
        visible_height = 32
        if self.height > visible_height:
            top = (self.height - visible_height) * scale
            img = img.crop((0, top, self.width * scale, self.height * scale))
        img.save(output_path)
        print(f"✓ Saved preview to {output_path}")
        return output_path

    def generate_animated_gif(self, output_path='christmas_animation.gif',
                            duration=5.0, fps=20):
        """
        Generate an animated GIF of the Christmas display
        duration: Length of animation in seconds
        fps: Frames per second
        """
        import os
        print(f"Generating animated GIF: {output_path}")
        print(f"Duration: {duration}s at {fps} FPS")

        from christmas_display import Snowflake

        # Create snowflakes
        num_snowflakes = 30
        snowflakes = [Snowflake(width=64, height=64) for _ in range(num_snowflakes)]

        frames = []
        num_frames = int(duration * fps)

        print(f"Rendering {num_frames} frames...")
        for frame_num in range(num_frames):
            # Render frame
            img = self.render_christmas_frame(
                blink_state=frame_num,
                snowflakes=snowflakes
            )
            frames.append(img)

            # Update snowflakes
            for flake in snowflakes:
                flake.fall()

            # Progress indicator
            if (frame_num + 1) % 20 == 0:
                print(f"  Rendered {frame_num + 1}/{num_frames} frames...")

        # Save as GIF
        print("Saving GIF...")
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=int(1000 / fps),  # Duration per frame in ms
            loop=0  # Loop forever
        )

        print(f"✓ Saved animation to {output_path}")
        print(f"  File size: {os.path.getsize(output_path) / 1024:.1f} KB")
        return output_path


def main():
    """Generate preview images and GIFs"""
    import os

    # Change to the display_control directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    simulator = DisplaySimulator(width=64, height=64)

    print("=" * 50)
    print("LED Matrix Display Simulator")
    print("=" * 50)
    print()

    # Generate static preview
    simulator.generate_static_preview('christmas_preview.png')
    print()

    # Generate power preview
    simulator.generate_power_preview('power_preview.png')
    print()

    # Generate short GIF (3 seconds)
    simulator.generate_animated_gif('christmas_animation.gif', duration=3.0, fps=20)
    print()

    print("=" * 50)
    print("Preview generation complete!")
    print("=" * 50)
    print()
    print("Generated files:")
    print("  - christmas_preview.png (static preview)")
    print("  - power_preview.png (static preview)")
    print("  - christmas_animation.gif (3s animation)")
    print()


if __name__ == "__main__":
    main()
