# Deploying to a new Pi

Tested against Raspberry Pi OS Bookworm (64-bit), user `pi`, HUB75 LED matrix.

```bash
sudo apt-get install -y git
git clone -b energy-dashboard https://github.com/nicolasj92/TrainTime.git ~/workspace/TrainTime
~/workspace/TrainTime/deploy/install.sh
nano ~/workspace/TrainTime/display_control/.env   # Home Assistant URL + token
sudo systemctl restart traintime
```

What it sets up:

| Piece | Where |
|---|---|
| `rpi-rgb-led-matrix` built at pinned commit, Python bindings installed system-wide | `~/workspace/rpi-rgb-led-matrix` |
| Python deps from apt (no venv): Pillow, numpy, requests, Flask, python-dotenv | system python3 |
| BDF fonts | `/usr/share/fonts/bdf` |
| `traintime.service` (root, runs `christmas_display.py`) | `/etc/systemd/system` |
| `display-control-web.service` (pi, Flask UI on :5000) | `/etc/systemd/system` |
| sudoers rule so the web UI can swap/restart `traintime.service` | `/etc/sudoers.d/display-control` |
| `dtparam=audio=off` | `/boot/firmware/config.txt` |

No cron jobs are used. The top-level `crontab`, `display_control.py` and `manage.py`
belong to the old Django version and aren't needed.
