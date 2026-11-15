#!/usr/bin/env python3
"""
Picture mode: shows the images in display_control/pictures/ (slideshow with crossfade).

- Files named like "dog_64x32.png" / "dog_32x32.png" are used as-is on the matching panel
  (prepare them cropped to exactly the panel size; that looks best).
- Other images (jpg/png) are centre-cropped to the panel and their shadows lifted a little,
  since LED panels show dark tones as almost off.

The pictures folder is gitignored (private photos). PICTURE_SECONDS sets the slideshow interval.
"""

import os
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from utils import Display, panel_config, run

PICTURE_DIR = Path(__file__).resolve().parent / "pictures"
SECONDS = float(os.getenv("PICTURE_SECONDS") or 20)
SIZED = re.compile(r"_(\d+)x(\d+)\.\w+$")


def prepare(path, width, height):
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if img.size == (width, height):
        return np.asarray(img)
    img = ImageOps.fit(img, (width, height), Image.LANCZOS)
    a = (np.asarray(img).astype(np.float32) / 255) ** 0.75          # lift shadows
    img = Image.fromarray((a * 255).astype(np.uint8))
    img = ImageEnhance.Color(ImageEnhance.Contrast(img).enhance(1.15)).enhance(1.3)
    return np.asarray(img)


def load_pictures():
    """Load before the LED library drops root privileges (it can't read /home/pi afterwards)."""
    cfg = panel_config()
    width, height = cfg["cols"] * cfg["chain"], cfg["rows"] * cfg["parallel"] - cfg["y_offset"]
    files = sorted(p for p in PICTURE_DIR.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif"))
    chosen = []
    for p in files:
        m = SIZED.search(p.name)
        if m and (int(m.group(1)), int(m.group(2))) != (width, height):
            continue  # made for the other panel size
        try:
            chosen.append(prepare(p, width, height))
        except Exception as e:
            print(f"Skipping {p.name}: {e}", flush=True)
    print(f"Loaded {len(chosen)} picture(s) for {width}x{height}", flush=True)
    return chosen


PICTURES = load_pictures()


class Picture:
    fps = 10
    fade_frames = 10

    def __init__(self, display: Display, pictures=None):
        self.d = display
        self.pictures = PICTURES if pictures is None else pictures
        self.frame_no = 0

    def frame(self):
        d = self.d
        if not self.pictures:
            d.clear()
            d.text(d.font_small, 0, 12, (200, 200, 200), "No pictures")
            d.text(d.font_small, 0, 20, (120, 120, 120), "display_control/")
            d.text(d.font_small, 0, 27, (120, 120, 120), "pictures/")
            return
        per_picture = max(1, int(SECONDS * self.fps))
        index, pos = divmod(self.frame_no, per_picture)
        current = self.pictures[index % len(self.pictures)]
        if len(self.pictures) > 1 and pos >= per_picture - self.fade_frames:
            nxt = self.pictures[(index + 1) % len(self.pictures)]
            t = (pos - (per_picture - self.fade_frames) + 1) / self.fade_frames
            current = (current * (1 - t) + nxt * t).astype(np.uint8)
        d.image(current)
        self.frame_no += 1


if __name__ == "__main__":
    run(Picture)
