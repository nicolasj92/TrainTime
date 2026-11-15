"""
Picture library for the Pictures mode, shared by the web UI (which edits it) and
picture_display.py (which shows it).

display_control/pictures/ (gitignored, private photos):
  <id>.jpg         the uploaded picture, upright, at most 1600 px
  <id>_thumb.jpg   small copy for the web UI
  library.json     {"pictures": [{"id", "name", "enabled", "crop": {"64x32": [x, y, w, h]}}]}

Crops are fractions of the picture's width/height, one per panel size, so the same library
works on 64x32 and 32x32 panels. Without a crop the picture is centre-cropped.
"""

import json
import re
import secrets
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

DIR = Path(__file__).resolve().parent / 'pictures'
LIBRARY = DIR / 'library.json'
TRANSITIONS = {'slide': 'Slide in from the right', 'fade': 'Crossfade', 'cut': 'Instant'}
_ID = re.compile(r'^[0-9a-f]{8}$')


def load():
    try:
        return json.loads(LIBRARY.read_text())
    except (OSError, ValueError):
        return {'pictures': []}


def save(lib):
    DIR.mkdir(exist_ok=True)
    tmp = LIBRARY.with_suffix('.tmp')
    tmp.write_text(json.dumps(lib, indent=1))
    tmp.replace(LIBRARY)


def add(img, name):
    """Store a PIL image (already upright) and append it to the library."""
    DIR.mkdir(exist_ok=True)
    pid = secrets.token_hex(4)
    img = img.convert('RGB')
    img.thumbnail((1600, 1600), Image.LANCZOS)
    img.save(DIR / f'{pid}.jpg', quality=90)
    thumb = img.copy()
    thumb.thumbnail((480, 480), Image.LANCZOS)
    thumb.save(DIR / f'{pid}_thumb.jpg', quality=82)
    entry = {'id': pid, 'name': Path(name).stem[:60], 'enabled': True, 'crop': {},
             'width': img.width, 'height': img.height}
    lib = load()
    lib['pictures'].append(entry)
    save(lib)
    return entry


def remove(pid):
    lib = load()
    before = len(lib['pictures'])
    lib['pictures'] = [p for p in lib['pictures'] if p['id'] != pid]
    if len(lib['pictures']) == before:
        return False
    save(lib)
    for f in (DIR / f'{pid}.jpg', DIR / f'{pid}_thumb.jpg'):
        f.unlink(missing_ok=True)
    return True


def update(pid, enabled=None, crop=None, move=None):
    lib = load()
    pics = lib['pictures']
    idx = next((i for i, p in enumerate(pics) if p['id'] == pid), None)
    if idx is None:
        return False
    if enabled is not None:
        pics[idx]['enabled'] = enabled
    if crop:
        pics[idx].setdefault('crop', {}).update(crop)
    if move:
        j = max(0, min(len(pics) - 1, idx + move))
        pics.insert(j, pics.pop(idx))
    save(lib)
    return True


def file_for(pid, thumb=False):
    if not _ID.match(pid):
        return None
    path = DIR / (f'{pid}_thumb.jpg' if thumb else f'{pid}.jpg')
    return path if path.exists() else None


def default_crop(img_w, img_h, panel_w, panel_h):
    """Largest centred box with the panel's aspect ratio, as fractions."""
    target = panel_w / panel_h
    if img_w / img_h > target:          # picture is wider than the panel
        w = img_h * target / img_w
        return [(1 - w) / 2, 0.0, w, 1.0]
    h = img_w / target / img_h
    return [0.0, (1 - h) / 2, 1.0, h]


def render(entry, panel_w, panel_h):
    """The picture as the panel shows it: cropped, scaled and tuned for LEDs (numpy uint8)."""
    img = Image.open(DIR / f"{entry['id']}.jpg").convert('RGB')
    x, y, w, h = entry.get('crop', {}).get(f'{panel_w}x{panel_h}') or \
        default_crop(img.width, img.height, panel_w, panel_h)
    box = (round(x * img.width), round(y * img.height), round((x + w) * img.width), round((y + h) * img.height))
    img = img.resize((panel_w, panel_h), Image.LANCZOS, box=box, reducing_gap=3.0)
    # LEDs show dark tones as almost off: lift shadows, a bit more contrast and colour
    a = (np.asarray(img).astype(np.float32) / 255) ** 0.75
    img = Image.fromarray((a * 255 + 0.5).astype(np.uint8))
    img = ImageEnhance.Color(ImageEnhance.Contrast(img).enhance(1.15)).enhance(1.3)
    return np.asarray(img)
