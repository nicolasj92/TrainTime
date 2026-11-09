"""
Stand-in for the `rgbmatrix` package, so the real display code runs on a normal computer.

simulator.py installs this as `rgbmatrix` before importing the display modes. Frames are kept
as numpy arrays instead of being sent to the LED panel. Text uses the same BDF fonts and
baseline rules as rpi-rgb-led-matrix.
"""

import numpy as np


class RGBMatrixOptions:
    def __init__(self):
        self.rows = 32
        self.cols = 32
        self.chain_length = 1
        self.parallel = 1
        self.gpio_slowdown = 1
        self.brightness = 100
        self.hardware_mapping = "regular"
        self.drop_privileges = True


class Canvas:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.pixels = np.zeros((height, width, 3), dtype=np.uint8)

    def SetPixel(self, x, y, r, g, b):
        x, y = int(x), int(y)
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y, x] = (r, g, b)

    def Clear(self):
        self.pixels.fill(0)

    def Fill(self, r, g, b):
        self.pixels[:] = (r, g, b)


class RGBMatrix:
    # Called with a copy of every frame passed to SwapOnVSync (set by the simulator)
    on_frame = None

    def __init__(self, options=None):
        options = options or RGBMatrixOptions()
        self.width = options.cols * options.chain_length
        self.height = options.rows * options.parallel
        self._spare = Canvas(self.width, self.height)

    def CreateFrameCanvas(self):
        return Canvas(self.width, self.height)

    def SwapOnVSync(self, canvas):
        if RGBMatrix.on_frame:
            RGBMatrix.on_frame(canvas.pixels.copy())
        # Like the real library, hand back the other buffer (with stale content)
        spare, self._spare = self._spare, canvas
        return spare


class _Graphics:
    class Color:
        def __init__(self, red=0, green=0, blue=0):
            self.red, self.green, self.blue = red, green, blue

    class Font:
        def __init__(self):
            self.glyphs = {}
            self.height = 0
            self.baseline = 0

        def LoadFont(self, path):
            glyph = None
            bitmap_rows = None
            with open(path, encoding="latin-1") as f:
                for line in f:
                    parts = line.split()
                    if not parts:
                        continue
                    key = parts[0]
                    if key == "FONTBOUNDINGBOX":
                        _, h, _, yoff = map(int, parts[1:5])
                        self.height = h
                        self.baseline = h + yoff
                    elif key == "ENCODING":
                        glyph = {"code": int(parts[1])}
                    elif key == "DWIDTH" and glyph is not None:
                        glyph["advance"] = int(parts[1])
                    elif key == "BBX" and glyph is not None:
                        glyph["w"], glyph["h"], glyph["xoff"], glyph["yoff"] = map(int, parts[1:5])
                    elif key == "BITMAP" and glyph is not None:
                        bitmap_rows = []
                    elif key == "ENDCHAR" and glyph is not None:
                        glyph["rows"] = bitmap_rows or []
                        self.glyphs[glyph["code"]] = glyph
                        glyph, bitmap_rows = None, None
                    elif bitmap_rows is not None:
                        bitmap_rows.append(int(key, 16) << (32 - 4 * len(key)) if key else 0)
            if not self.glyphs:
                raise Exception(f"Couldn't load font {path}")

        def CharacterWidth(self, code):
            g = self.glyphs.get(code)
            return g["advance"] if g else -1

    @staticmethod
    def DrawText(canvas, font, x, y, color, text):
        start = x
        for ch in text:
            g = font.glyphs.get(ord(ch))
            if g is None:
                continue
            top = y - (g["h"] + g["yoff"])
            for r, bits in enumerate(g["rows"]):
                for c in range(g["w"]):
                    if bits & (1 << (31 - c)):
                        canvas.SetPixel(x + g["xoff"] + c, top + r, color.red, color.green, color.blue)
            x += g["advance"]
        return x - start

    @staticmethod
    def DrawLine(canvas, x0, y0, x1, y1, color):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            canvas.SetPixel(x0, y0, color.red, color.green, color.blue)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy


graphics = _Graphics()
