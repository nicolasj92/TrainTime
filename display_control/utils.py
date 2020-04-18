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

font_dir = os.path.join(Path(__file__).parent.absolute(), "fonts")


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


class Display:
    def __init__(self, interval=0.05):
        options = RGBMatrixOptions()
        options.chain_length = 2
        options.gpio_slowdown = 4
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
            self.offscreen_canvas, self.font_large, 20, 6, self.textColor, time_str
        )
        icon_error = IconError(self.offscreen_canvas, 28, 10)
        icon_error.draw()
        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 0, 24, self.textColor, error_message
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
            for j, connection in enumerate(route_information[i][2][:3]):
                if connection.vehicle_type == "Bus":
                    icon_bus = IconBus(self.offscreen_canvas, i * 32, j * 8 + 8)
                    icon_bus.draw()
                elif connection.vehicle_type == "Tram":
                    icon_tram = IconTram(self.offscreen_canvas, i * 32, j * 8 + 8)
                    icon_tram.draw()

                graphics.DrawText(
                    self.offscreen_canvas,
                    self.font_small,
                    i * 32 + 9,
                    j * 8 + 14,
                    self.textColor,
                    "{}-{}".format(
                        connection.line_name[:3], connection.get_timediff_from_now_min()
                    ),
                )

        graphics.DrawText(
            self.offscreen_canvas, self.font_large, 20, 6, self.textColor, time_str
        )
        graphics.DrawText(
            self.offscreen_canvas, self.font_small, 0, 6, self.textColor, "HBF"
        )
        graphics.DrawText(
            self.offscreen_canvas, self.font_small, 50, 6, self.textColor, "LiWi"
        )

        time.sleep(self.interval)
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
