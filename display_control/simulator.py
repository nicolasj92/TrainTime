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


class FixedWeather:
    def __init__(self, **values):
        from sky_display import FAIR
        self.now = {**FAIR, **values}


WEATHER_SAMPLES = [  # (label, hour, minute, weather)
    ("clear", 12, 30, dict(clouds=0.0)),
    ("some clouds", 12, 30, dict(clouds=0.35)),
    ("overcast", 12, 30, dict(clouds=0.95)),
    ("rain", 12, 30, dict(clouds=1.0, rain=2.0)),
    ("snow", 12, 30, dict(clouds=1.0, snow=1.0)),
    ("cloudy night", 22, 0, dict(clouds=0.5)),
]


def sheet(images, gap=20):
    w, h = images[0].size
    out = Image.new("RGB", (w * len(images) + gap * (len(images) - 1), h), (60, 60, 60))
    for i, im in enumerate(images):
        out.paste(im, (i * (w + gap), 0))
    return out


def render_sky(size, out_dir, gif=False):
    """Sky clock: four moments of one day, the weather variants, and an optional 24-hour time-lapse."""
    from zoneinfo import ZoneInfo
    from sky_display import Sky
    os.environ["LED_PANEL"] = size
    cap = Capture()
    d = cap.display()
    day = datetime(2026, 11, 15, tzinfo=ZoneInfo("Europe/Berlin"))
    clock = {"t": day}
    strip = []
    m = Sky(d, now=lambda: clock["t"], weather=FixedWeather())
    for hh, mm in [(1, 30), (7, 25), (12, 30), (16, 50)]:
        clock["t"] = day.replace(hour=hh, minute=mm)
        for _ in range(3):
            m.frame()
            d.swap()
        strip.append(to_image(cap.frames[-1]))
    png = out_dir / f"sky_{size}.png"
    sheet(strip).save(png)
    print(f"wrote {png.relative_to(HERE)}  (01:30, 07:25, 12:30, 16:50 on 15 Nov)")

    variants = []
    for label, hh, mm, weather in WEATHER_SAMPLES:
        clock["t"] = day.replace(hour=hh, minute=mm)
        m = Sky(d, now=lambda: clock["t"], weather=FixedWeather(**weather))
        for _ in range(40):                      # let rain/snow fill the sky
            m.frame()
            d.swap()
        variants.append(to_image(cap.frames[-1]))
    png = out_dir / f"sky_weather_{size}.png"
    sheet(variants).save(png)
    print(f"wrote {png.relative_to(HERE)}  ({', '.join(v[0] for v in WEATHER_SAMPLES)})")

    if gif:
        cap.frames.clear()
        m = Sky(d, now=lambda: clock["t"], weather=FixedWeather(clouds=0.3))
        for i in range(144):                      # every 10 minutes
            clock["t"] = day + timedelta(minutes=10 * i)
            m.frame()
            d.swap()
        imgs = [to_image(f, scale=6) for f in cap.frames]
        out = out_dir / f"sky_{size}.gif"
        imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=80, loop=0)
        print(f"wrote {out.relative_to(HERE)}  (24 h time-lapse)")


def render(mode, size, out_dir, frames_for_gif=0):
    if mode == "sky":
        return render_sky(size, out_dir, gif=bool(frames_for_gif))
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
        m = utils.WifiSetupScreen(d, "pidisplay-setup", "k3x9m2qa", "10.42.0.1")
        m.fps = 15
        warmup = 12
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
    parser.add_argument("--mode", choices=["christmas", "power", "departures", "sky", "wifi", "all"], default="all")
    parser.add_argument("--gif", action="store_true", help="also write animated GIFs (christmas, sky time-lapse)")
    args = parser.parse_args()
    out_dir = HERE / "previews"
    out_dir.mkdir(exist_ok=True)
    sizes = list(PANEL_PRESETS) if args.size == "all" else [args.size]
    modes = ["christmas", "power", "departures", "sky", "wifi"] if args.mode == "all" else [args.mode]
    for size in sizes:
        for mode in modes:
            render(mode, size, out_dir, frames_for_gif=80 if (args.gif and mode in ("christmas", "sky")) else 0)


if __name__ == "__main__":
    main()
