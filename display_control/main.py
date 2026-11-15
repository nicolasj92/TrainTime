#!/usr/bin/env python3
"""
Entry point of traintime.service: starts the display mode chosen in .env (DISPLAY_MODE),
e.g. DISPLAY_MODE=sky runs sky_display.py. The web UI changes DISPLAY_MODE and restarts the service.
"""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
mode = (dotenv_values(HERE / '.env').get('DISPLAY_MODE') or 'sky').strip()
script = HERE / f'{mode}_display.py'
if not script.is_file():
    print(f"Unknown DISPLAY_MODE={mode!r}, using sky", flush=True)
    script = HERE / 'sky_display.py'
os.chdir(HERE)
os.execv(sys.executable, [sys.executable, str(script)])
