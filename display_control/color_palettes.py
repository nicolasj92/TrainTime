"""
Palettes for the Ambient Colors mode, shared with the web UI (which shows them as swatches).

COLORS_PALETTES: which palettes to cycle through, comma-separated (empty = all built-in ones).
COLORS_CUSTOM:   your own palette, 2-6 colours like #1a2b3c,#ff8800 (used when "custom" is selected).
"""

import re

PALETTES = {                                      # colours blend smoothly in a loop
    "aurora": [(20, 60, 110), (30, 200, 150), (140, 90, 230), (60, 230, 200)],
    "sunset": [(110, 30, 110), (240, 70, 80), (255, 165, 60), (200, 50, 120)],
    "ocean": [(20, 50, 150), (30, 140, 220), (80, 220, 210), (40, 90, 200)],
    "lavender": [(80, 50, 170), (170, 100, 230), (250, 150, 200), (120, 80, 210)],
    "forest": [(30, 90, 50), (80, 170, 70), (220, 210, 90), (40, 140, 110)],
    "fire": [(120, 20, 10), (240, 90, 20), (255, 190, 60), (180, 40, 30)],
    "candy": [(250, 120, 170), (120, 200, 250), (250, 220, 120), (180, 140, 250)],
    "ice": [(150, 200, 240), (60, 120, 210), (220, 235, 250), (90, 170, 220)],
}
DEFAULT_CUSTOM = "#ff5e62,#ff9966,#6a82fb,#fc5c7d"


def parse_colors(text):
    """'#ff0000,#00ff00' -> [(255, 0, 0), (0, 255, 0)]; invalid entries are skipped."""
    out = []
    for part in (text or "").split(","):
        part = part.strip().lstrip("#")
        if re.fullmatch(r"[0-9a-fA-F]{6}", part):
            out.append(tuple(int(part[i:i + 2], 16) for i in (0, 2, 4)))
    return out[:6]


def selected(names_setting, custom_setting):
    """The palettes to cycle through, in order: list of (name, colours)."""
    names = [n.strip() for n in (names_setting or "").split(",") if n.strip()] or list(PALETTES)
    chosen = []
    for name in names:
        if name == "custom":
            colors = parse_colors(custom_setting or DEFAULT_CUSTOM)
            if len(colors) >= 2:
                chosen.append((name, colors))
        elif name in PALETTES:
            chosen.append((name, PALETTES[name]))
    return chosen or list(PALETTES.items())


def css_gradient(colors):
    stops = list(colors) + [colors[0]]
    return "linear-gradient(90deg, " + ", ".join(f"rgb{tuple(c)}" for c in stops) + ")"
