#!/usr/bin/env python3
"""
Render previews of every display mode without LED hardware.

Runs the real mode code against fake_rgbmatrix with sample data, for each panel size.
Needs numpy, Pillow and python-dotenv (not the rgbmatrix library).

    python3 simulator.py                      # all modes, all sizes -> previews/
    python3 simulator.py --size 32x32 --mode departures
"""

import argparse
import os
import random
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["FONT_DIR"] = str(HERE / "fonts")
os.environ.setdefault("LED_GPIO_SLOWDOWN", "1")

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import fake_rgbmatrix  # noqa: E402

_fake = types.ModuleType("rgbmatrix")
_fake.RGBMatrix = fake_rgbmatrix.RGBMatrix
_fake.RGBMatrixOptions = fake_rgbmatrix.RGBMatrixOptions
_fake.graphics = fake_rgbmatrix.graphics
sys.modules["rgbmatrix"] = _fake

import utils  # noqa: E402
from utils import PANEL_PRESETS, Display  # noqa: E402

SCALE = 10
GAP = 2  # dark pixels between LEDs, so previews look like a panel


def to_image(pixels, scale=SCALE):
    """Upscale a frame and draw each pixel as a round-ish LED."""
    h, w, _ = pixels.shape
    img = np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
    mask = np.ones((scale, scale), dtype=bool)
    mask[:GAP // 2, :] = mask[scale - GAP // 2:, :] = False
    mask[:, :GAP // 2] = mask[:, scale - GAP // 2:] = False
    img[~np.tile(mask, (h, w))] = 15
    return Image.fromarray(img)


class Capture:
    def __init__(self):
        self.frames = []
        fake_rgbmatrix.RGBMatrix.on_frame = self.on_frame
        self.y_offset = 0
        self.height = 0

    def on_frame(self, pixels):
        self.frames.append(pixels[self.y_offset:self.y_offset + self.height])

    def display(self):
        d = Display()
        self.y_offset, self.height = d.y_offset, d.height
        return d


def sample_power(solar, grid):
    return types.SimpleNamespace(solar=solar, grid=grid, home=solar + grid, error=None)


def sample_departures():
    import departures_display as dd
    now = datetime.now(dd.RMV_TZ).replace(second=0, microsecond=0)
    def dep(line, cat, label, idx, minutes, delay=0, cancelled=False):
        planned = now + timedelta(minutes=minutes)
        return dd.Departure(line, cat, "", label, idx, planned,
                            planned + timedelta(minutes=delay), cancelled)
    return types.SimpleNamespace(error=None, updated=0, departures=[
        dep("1", "Bus", "Hauptbahnhof", 0, 0),           # too soon to reach, hidden
        dep("9", "Tram", "Hbf", 0, 3),
        dep("4", "Tram", "LiWi", 1, 5, delay=3),
        dep("671", "Bus", "LiWi", 1, 12),
        dep("S3", "S", "Hbf", 0, 14, cancelled=True),
    ])


def render(mode, size, out_dir, frames_for_gif=0):
    os.environ["LED_PANEL"] = size
    cap = Capture()
    d = cap.display()
    random.seed(3)
    if mode == "christmas":
        from christmas_display import Christmas
        m = Christmas(d)
        m.frames_until_plow = 520          # bring the plow in during the preview
        warmup = 600
    elif mode == "power":
        from power_display import PowerFlow
        m = PowerFlow(d, source=sample_power(solar=820, grid=-240))
        warmup = 3
    elif mode == "departures":
        from departures_display import Departures
        m = Departures(d, source=sample_departures())
        warmup = 1
    elif mode == "wifi":
        d.message(["Setup", "WiFi:", "pidisplay-setup", "pw: 1a2b3c4d"], icon=utils.IconWifi)
        m, warmup = None, 0
    else:
        raise ValueError(mode)

    for _ in range(warmup + frames_for_gif):
        m.frame()
        d.swap()
    png = out_dir / f"{mode}_{size}.png"
    to_image(cap.frames[warmup - 1 if warmup else -1]).save(png)
    print(f"wrote {png.relative_to(HERE)}")
    if frames_for_gif:
        gif = out_dir / f"{mode}_{size}.gif"
        imgs = [to_image(f, scale=6) for f in cap.frames[warmup:]]
        imgs[0].save(gif, save_all=True, append_images=imgs[1:], duration=int(1000 / m.fps), loop=0)
        print(f"wrote {gif.relative_to(HERE)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", choices=[*PANEL_PRESETS, "all"], default="all")
    parser.add_argument("--mode", choices=["christmas", "power", "departures", "wifi", "all"], default="all")
    parser.add_argument("--gif", action="store_true", help="also write an animated GIF of christmas")
    args = parser.parse_args()
    out_dir = HERE / "previews"
    out_dir.mkdir(exist_ok=True)
    sizes = list(PANEL_PRESETS) if args.size == "all" else [args.size]
    modes = ["christmas", "power", "departures", "wifi"] if args.mode == "all" else [args.mode]
    for size in sizes:
        for mode in modes:
            render(mode, size, out_dir, frames_for_gif=80 if (args.gif and mode == "christmas") else 0)


if __name__ == "__main__":
    main()
