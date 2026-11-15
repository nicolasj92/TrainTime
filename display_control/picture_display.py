#!/usr/bin/env python3
"""
Pictures mode: a slideshow of the pictures ticked on the web UI's Pictures page.

PICTURE_SECONDS sets how long each picture stays, PICTURE_TRANSITION how the next one
comes in (slide, fade or cut). See pictures.py for how the library is stored.
"""

import os

import numpy as np

import pictures as library
from utils import Display, panel_config, run

SECONDS = max(1.0, float(os.getenv("PICTURE_SECONDS") or 20))
TRANSITION = os.getenv("PICTURE_TRANSITION") or "slide"
TRANSITION_SECONDS = 0.9


def panel_size():
    cfg = panel_config()
    return cfg["cols"] * cfg["chain"], cfg["rows"] * cfg["parallel"] - cfg["y_offset"]


def load_pictures():
    """Load before the LED library drops root privileges (it can't read /home/pi afterwards)."""
    width, height = panel_size()
    frames = []
    for entry in library.load()["pictures"]:
        if entry.get("enabled", True):
            try:
                frames.append(library.render(entry, width, height).astype(np.float32))
            except Exception as e:
                print(f"Skipping {entry.get('name')}: {e!r}", flush=True)
    print(f"Loaded {len(frames)} picture(s) for {width}x{height}, {SECONDS:g}s each, {TRANSITION}", flush=True)
    return frames


PICTURES = load_pictures()


def ease(t):
    """Smooth start and stop (cubic ease-in-out)."""
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def slide(current, nxt, t):
    """Next picture pushes the current one out to the left; sub-pixel steps keep it smooth."""
    width = current.shape[1]
    strip = np.concatenate([current, nxt], axis=1)
    shift = ease(t) * width
    whole, frac = int(shift), shift - int(shift)
    a = strip[:, whole:whole + width]
    b = strip[:, min(whole + 1, width):min(whole + 1, width) + width]
    return a * (1 - frac) + b * frac


class Picture:
    fps = 4                        # still pictures need few frames; transitions run at 40 fps

    def __init__(self, display: Display, pictures=None, transition=TRANSITION, seconds=SECONDS):
        self.d = display
        self.pictures = PICTURES if pictures is None else pictures
        self.transition = transition if transition in library.TRANSITIONS else "slide"
        self.seconds = seconds
        self.index = 0
        self.shown = 0.0           # seconds the current picture has been on
        self.progress = None       # 0..1 while a transition runs

    def frame(self):
        d = self.d
        if not self.pictures:
            d.clear()
            d.text(d.font_small, 0, 10, (200, 200, 200), "No pictures")
            d.text(d.font_small, 0, 18, (120, 120, 120), "Add some on")
            d.text(d.font_small, 0, 25, (120, 120, 120), "the web page")
            return
        current = self.pictures[self.index % len(self.pictures)]
        if len(self.pictures) == 1:
            d.image(current.astype(np.uint8))
            return
        if self.progress is None:
            d.image(current.astype(np.uint8))
            self.shown += 1 / self.fps
            if self.shown >= self.seconds:
                if self.transition == "cut":
                    self._advance()
                else:
                    self.progress, self.fps = 0.0, 40
            return
        nxt = self.pictures[(self.index + 1) % len(self.pictures)]
        self.progress = min(1.0, self.progress + 1 / (TRANSITION_SECONDS * self.fps))
        if self.transition == "fade":
            t = ease(self.progress)
            frame = current * (1 - t) + nxt * t
        else:
            frame = slide(current, nxt, self.progress)
        d.image(np.clip(frame + 0.5, 0, 255).astype(np.uint8))
        if self.progress >= 1.0:
            self._advance()

    def _advance(self):
        self.index = (self.index + 1) % len(self.pictures)
        self.shown, self.progress, self.fps = 0.0, None, 4


if __name__ == "__main__":
    run(Picture)
