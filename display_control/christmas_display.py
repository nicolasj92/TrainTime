#!/usr/bin/env python3
"""
Christmas Display for LED Matrix
Shows current time with falling snow animation, snow accumulation, and snowplow
"""

import time
import random
import socket
from utils import Display

# Socket-based locking to prevent multiple instances
def get_lock():
    """Create a socket-based lock to ensure only one instance runs"""
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        # Use abstract namespace (Linux-specific)
        lock_socket.bind('\0christmas_display_daemon')
        return lock_socket
    except socket.error:
        print('Another instance of christmas_display.py is already running')
        return None


class Snowflake:
    """Represents a single falling snowflake"""
    def __init__(self, width=64, height=64):
        self.x = random.randint(0, width - 1)
        self.y = random.randint(-height // 2, 0)  # Start above screen
        self.speed = random.choice([0.08, 0.12, 0.16])  # Even slower fall speeds
        self.drift = random.choice([-0.15, 0, 0.15])  # Even slower horizontal drift
        self.width = width
        self.height = height
        self.y_float = float(self.y)  # Keep track of sub-pixel position

    def fall(self):
        """Move the snowflake down"""
        self.y_float += self.speed
        self.y = int(self.y_float)
        # Add horizontal drift occasionally
        if random.random() < 0.2:
            self.x += int(self.drift)
            # Keep within bounds
            self.x = max(0, min(self.width - 1, self.x))

        # Reset to top if fallen off screen
        if self.y >= self.height:
            self.y = random.randint(-10, 0)
            self.y_float = float(self.y)
            self.x = random.randint(0, self.width - 1)

    def is_visible(self):
        """Check if snowflake is currently on screen"""
        return 0 <= self.y < self.height


def main():
    # Get lock to prevent multiple instances
    lock = get_lock()
    if lock is None:
        return

    print("Starting Christmas display...")
    display = Display(interval=0.02)

    # Create snowflakes
    num_snowflakes = 30
    snowflakes = [Snowflake(width=64, height=64) for _ in range(num_snowflakes)]

    # Snow accumulation at bottom (x-coordinate -> height)
    snow_accumulation = {x: 0 for x in range(64)}

    # Snowplow state
    plow_width = 10
    plow_blade = 3
    plow_active = False
    plow_position = -(plow_width + plow_blade)
    plow_direction = 1
    frames_until_plow = random.randint(1000, 2000)  # Plow comes every 50-100 seconds at 20fps

    blink_counter = 0
    roof_overhang = 2
    houses = [
        {"x": 8, "y": 53, "w": 9, "h": 6, "roof_h": 2, "windows": [(1, 2, 2, 2), (5, 2, 2, 2)], "roof_snow": [0] * (9 + roof_overhang * 2), "chimney_snow": 0, "window_level": 80, "target_level": 90},
        {"x": 44, "y": 57, "w": 10, "h": 6, "roof_h": 3, "windows": [(1, 2, 2, 2), (6, 2, 2, 2)], "roof_snow": [0] * (10 + roof_overhang * 2), "chimney_snow": 0, "window_level": 90, "target_level": 110},
    ]

    def _matrix_dim(attr, fallback):
        value = getattr(display.matrix, attr, fallback)
        if callable(value):
            value = value()
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    try:
        while True:
            # Check if we should activate the snowplow
            if not plow_active:
                frames_until_plow -= 1
                if frames_until_plow <= 0:
                    plow_active = True
                    plow_direction = random.choice([1, -1])
                    if plow_direction == 1:
                        plow_position = -(plow_width + plow_blade)
                    else:
                        plow_position = 64 + plow_blade

            # Update snowplow position (slower movement)
            if plow_active and blink_counter % 2 == 0:  # Move every other frame
                plow_position += plow_direction
                # Clear snow where plow passes
                if plow_direction == 1:
                    clear_start = plow_position
                    clear_end = plow_position + plow_width + plow_blade - 1
                else:
                    clear_start = plow_position - plow_blade
                    clear_end = plow_position + plow_width - 1
                for px in range(clear_start, clear_end + 1):
                    if 0 <= px < 64:
                        snow_accumulation[px] = 0

                # Deactivate plow when it reaches the end
                if plow_direction == 1 and plow_position > 64:
                    plow_active = False
                    frames_until_plow = random.randint(1000, 2000)
                elif plow_direction == -1 and plow_position + plow_width < 0:
                    plow_active = False
                    frames_until_plow = random.randint(1000, 2000)

            # Draw the Christmas scene with snow accumulation
            display.print_christmas(
                blink_state=blink_counter,
                snow_accumulation=snow_accumulation,
                plow_position=plow_position if plow_active else None,
                plow_direction=plow_direction,
                houses=houses,
            )

            # Update house window flicker and roof snow
            for house in houses:
                if blink_counter % 8 == 0:
                    house["target_level"] = random.randint(50, 170)
                if house["window_level"] < house["target_level"]:
                    house["window_level"] += 2
                elif house["window_level"] > house["target_level"]:
                    house["window_level"] -= 2
                house["window_level"] = max(40, min(190, house["window_level"] + random.randint(-3, 3)))

            # Draw falling snow with smooth brightness transitions
            for flake in snowflakes:
                if flake.is_visible():
                    # Check if snowflake hits accumulated snow or ground
                    if flake.y >= 63 or (flake.y >= 63 - snow_accumulation.get(flake.x, 0)):
                        # Add to accumulation (max height of 10 pixels)
                        if snow_accumulation[flake.x] < 10:
                            snow_accumulation[flake.x] += 1
                        # Reset snowflake to top
                        flake.y = random.randint(-10, 0)
                        flake.y_float = float(flake.y)
                        flake.x = random.randint(0, 63)
                    else:
                        # Check if snowflake hits a house roof
                        hit_house = False
                        for house in houses:
                            if house["x"] - roof_overhang <= flake.x < house["x"] + house["w"] + roof_overhang:
                                idx = flake.x - house["x"] + roof_overhang
                                if idx < 0 or idx >= len(house["roof_snow"]):
                                    continue
                                roof_base_y = house["y"] - house["h"]
                                peak_x = house["x"] + house["w"] // 2
                                slope = house["roof_h"] - (abs(flake.x - peak_x) + 1) // 2
                                if slope < 0:
                                    continue
                                roof_y = roof_base_y - slope - 1
                                chimney_x = house["x"] + house["w"] - 2
                                chimney_base = roof_base_y - house["roof_h"] + 1
                                chimney_top = chimney_base - 3
                                chimney_snow = house.get("chimney_snow", 0)
                                if flake.x == chimney_x:
                                    if chimney_snow < 2 and chimney_top <= flake.y <= chimney_top + 1:
                                        house["chimney_snow"] = chimney_snow + 1
                                        flake.y = random.randint(-10, 0)
                                        flake.y_float = float(flake.y)
                                        flake.x = random.randint(0, 63)
                                        hit_house = True
                                        break
                                snow_depth = house["roof_snow"][idx]
                                if flake.y >= roof_y - snow_depth and flake.y <= roof_y:
                                    if house["roof_snow"][idx] < 2:
                                        house["roof_snow"][idx] += 1
                                    flake.y = random.randint(-10, 0)
                                    flake.y_float = float(flake.y)
                                    flake.x = random.randint(0, 63)
                                    hit_house = True
                                    break
                        if hit_house:
                            flake.fall()
                            continue

                        # Check if snowflake is in time display area (skip drawing if so)
                        # Time is at position (20, 38) with font size roughly 25x7 pixels
                        in_time_area = (18 <= flake.x <= 45 and 32 <= flake.y <= 39)
                        if not in_time_area:
                            # Draw snowflake with smooth sub-pixel positioning
                            # Calculate brightness based on sub-pixel position
                            fraction = flake.y_float - flake.y  # 0.0 to 1.0

                            # Main pixel (current position)
                            brightness_main = max(0, min(255, int(255 * (1.0 - fraction * 0.5))))
                            display.offscreen_canvas.SetPixel(
                                flake.x, flake.y,
                                brightness_main, brightness_main, brightness_main
                            )

                            # Next pixel (below) with fade-in effect
                            if flake.y + 1 < 64:
                                brightness_next = max(0, min(255, int(255 * fraction * 0.5)))
                                if brightness_next > 0:
                                    display.offscreen_canvas.SetPixel(
                                        flake.x, flake.y + 1,
                                        brightness_next, brightness_next, brightness_next
                                    )

                # Move snowflake
                flake.fall()

            # Swap buffers to show the frame
            display.offscreen_canvas = display.matrix.SwapOnVSync(display.offscreen_canvas)

            # Increment blink counter for animations
            blink_counter += 1

            # Gradually melt snow (slowly)
            if blink_counter % 100 == 0:
                # Reduce snow height at random positions
                for _ in range(2):  # Melt 2 random positions
                    x = random.randint(0, 63)
                    if snow_accumulation[x] > 0:
                        snow_accumulation[x] -= 1
            if blink_counter % 200 == 0:
                for house in houses:
                    if house["roof_snow"]:
                        melt_idx = random.randint(0, len(house["roof_snow"]) - 1)
                        if house["roof_snow"][melt_idx] > 0:
                            house["roof_snow"][melt_idx] -= 1
                    if house.get("chimney_snow", 0) > 0 and random.random() < 0.5:
                        house["chimney_snow"] -= 1

            # Small delay for animation timing
            time.sleep(0.05)  # ~20 FPS

    except KeyboardInterrupt:
        print("\nStopping Christmas display...")
        display.offscreen_canvas.Clear()
        display.matrix.SwapOnVSync(display.offscreen_canvas)
    finally:
        if lock:
            lock.close()


if __name__ == "__main__":
    main()
