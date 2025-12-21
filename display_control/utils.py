import time
import numpy as np
import os
from datetime import datetime
from pathlib import Path

from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

color_blue = [48, 118, 179]
color_black = [0, 0, 0]
color_yellow = [255, 255, 0]
color_orange = [214, 130, 53]
color_red = [255, 0, 0]

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


class Display:
    def __init__(self, interval=0.05):
        options = RGBMatrixOptions()
        options.chain_length = 2
        options.gpio_slowdown = 4
        options.parallel = 2
        self.matrix = RGBMatrix(options=options)
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()

        self.font_small = graphics.Font()
        self.font_small.LoadFont(os.path.join(font_dir, "4x6.bdf"))
        self.font_large = graphics.Font()
        self.font_large.LoadFont(os.path.join(font_dir, "5x7.bdf"))
        self.textColor = graphics.Color(255, 255, 255)

        self.interval = interval

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
        Display power flow information with animated lines showing power direction
        solar_power: Current solar production in watts
        home_power: Current home consumption in watts
        grid_power: Current grid power (positive for consumption, negative for feed-in)
        """
        # Calculate power flow directions (do this once outside the loop)
        solar_to_home = min(solar_power, home_power)
        solar_to_grid = max(0, solar_power - home_power)
        grid_to_home = max(0, home_power - solar_power)

        # Animation loop
        start_time = time.time()
        while (time.time() - start_time) < 2.0:  # Run for 2 seconds before allowing updates
            self.offscreen_canvas.Clear()
            
            # Define colors - using blue/grey theme
            base_color = (60, 100, 160)  # Darker blue/grey for base lines
            bright_color = (100, 149, 237)  # Brighter blue for dashes
            text_color = graphics.Color(255, 255, 255)  # White for text
            
            # Define positions for the components
            solar_x, solar_y = 52, 32 + 6  # Solar aligned with house position
            grid_x, grid_y = 12, 32 + 18  # Grid connection point moved up 2 pixels
            home_x, home_y = 52, 32 + 18  # Home connection point moved up 2 pixels
            
            # Draw time in top left with boundary
            time_str = datetime.now().strftime("%H:%M")
            time_width = len(time_str) * 5  # 5 pixels per character for large font
            time_height = 7  # Height of large font
            
            # Draw boundary box
            for x in range(-1, time_width + 1):
                for y in range(31, 32 + time_height + 1):
                    if x == -1 or x == time_width or y == 31 or y == 32 + time_height:
                        self.offscreen_canvas.SetPixel(x, y, *base_color)
            
            # Draw time text
            graphics.DrawText(
                self.offscreen_canvas, self.font_large, 0, 32 + 6, text_color, time_str
            )
            
            # Draw sun icon (positioned dynamically)
            solar_text = f"{solar_power}W"
            solar_width = len(solar_text) * 4  # 4 pixels per character for small font
            solar_x_icon = 64 - solar_width  # Position of solar text
            
            # Draw sun icon (positioned dynamically)
            sun_icon = IconSun(self.offscreen_canvas, solar_x_icon - 12, 32)  # 12 pixels left of solar text
            sun_icon.draw()
            
            # Draw solar text
            graphics.DrawText(
                self.offscreen_canvas, self.font_large, solar_x, 32 + 6, text_color, solar_text
            )
            
            # Draw house icon (positioned halfway between previous positions)
            house_icon = IconHouse(self.offscreen_canvas, home_x + 2, 32 + 14)
            house_icon.draw()
            
            # Draw grid icon
            grid_icon = IconGrid(self.offscreen_canvas, grid_x - 8, 32 + 14)
            grid_icon.draw()
            
            # Display power values
            # Solar power (right-aligned)
            solar_text = f"{solar_power}W"
            solar_width = len(solar_text) * 6  # 4 pixels per character for small font
            solar_x = 64 - solar_width  # Position of solar text
            
            # Draw solar text
            graphics.DrawText(
                self.offscreen_canvas, self.font_large, solar_x, 32 + 6, text_color, solar_text
            )
            
            # Home power (right-aligned)
            home_text = f"{home_power}W"
            home_width = len(home_text) * 6
            graphics.DrawText(
                self.offscreen_canvas, self.font_large, 64 - home_width, home_y + 12, text_color, home_text
            )
            
            # Grid power (left-aligned)
            grid_text = f"{abs(grid_power)}W"
            graphics.DrawText(
                self.offscreen_canvas, self.font_large, grid_x - 8, grid_y + 12, text_color, grid_text
            )

            def draw_thick_pixel(x, y, color, is_bright):
                # Draw a 2x2 pixel line (wider horizontally)
                if is_bright:
                    # Draw bright pixels first
                    self.offscreen_canvas.SetPixel(x, y, *bright_color)
                    self.offscreen_canvas.SetPixel(x + 1, y, *bright_color)
                    self.offscreen_canvas.SetPixel(x, y + 1, *bright_color)
                    self.offscreen_canvas.SetPixel(x + 1, y + 1, *bright_color)
                else:
                    # Draw base color pixels
                    self.offscreen_canvas.SetPixel(x, y, *color)
                    self.offscreen_canvas.SetPixel(x + 1, y, *color)
                    self.offscreen_canvas.SetPixel(x, y + 1, *color)
                    self.offscreen_canvas.SetPixel(x + 1, y + 1, *color)

            # Animation offset (0-7 for 8-pixel dash pattern)
            offset = int((time.time() * 6) % 8)  # Faster animation speed
            
            # Draw animated dashed lines
            # Solar to Home straight down
            if solar_to_home > 0:
                for i in range(100):  # Much higher resolution for longer line
                    x = solar_x + int((home_x - solar_x) * i / 100)
                    y = solar_y + int((home_y - solar_y) * i / 100)
                    # Draw thicker line
                    is_bright = (i + offset) % 8 < 4  # Move from solar to home
                    draw_thick_pixel(x, y, base_color, is_bright)
            
            # Solar to Grid (diagonal left)
            if solar_to_grid > 0:
                for i in range(40):  # Increased resolution
                    x = solar_x + int((grid_x - solar_x) * i / 40)
                    y = solar_y + int((grid_y - solar_y) * i / 40)
                    # Draw thicker line
                    is_bright = (i -  offset) % 8 < 4  # Move from solar to grid
                    draw_thick_pixel(x, y, base_color, is_bright)
            
            # Grid to Home (horizontal)
            if grid_to_home > 0:
                # Make sure we iterate in the correct direction if grid_x > home_x
                start_x = min(grid_x, home_x)
                end_x   = max(grid_x, home_x)

                # Compute an animation offset so the dashes move over time
                offset = int((time.time() * 6) % 8)

                for x in range(start_x, end_x):
                    # Decide whether this pixel is bright or base color
                    # Add offset if you want left->right flow, subtract offset if you want right->left flow
                    is_bright = ((x - offset) % 8) < 4

                    # Draw at (x, grid_y); 2×2 for thickness
                    draw_thick_pixel(x, grid_y, base_color, is_bright)
            
            self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
            time.sleep(0.02)  # Faster refresh rate


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
