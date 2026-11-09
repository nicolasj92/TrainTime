# TrainTime

Software for a 64×64 RGB LED matrix driven by a Raspberry Pi (`pidisplay`).
It shows animated displays you can switch between from a small web page on the Pi.

![Christmas mode](display_control/christmas_animation.gif)

## Display modes

| Mode | Script | What it shows |
|---|---|---|
| Christmas Snow | `display_control/christmas_display.py` | Clock with falling snow that piles up, melts and gets cleared by a snowplow |
| Power Flow | `display_control/power_display.py` | Live solar / grid / house power from Home Assistant, with animated flow arrows |

Only one mode runs at a time, as `traintime.service`. You switch modes from the web page at
**http://pidisplay.local:5000** (`display_control/web_control.py`). It rewrites the service
file and restarts the service.

## Quick start (new Pi)

On Raspberry Pi OS Bookworm (64-bit), logged in as user `pi`:

```bash
sudo apt-get install -y git
git clone -b energy-dashboard https://github.com/nicolasj92/TrainTime.git ~/workspace/TrainTime
~/workspace/TrainTime/deploy/install.sh
nano ~/workspace/TrainTime/display_control/.env   # only needed for Power Flow mode
sudo systemctl restart traintime
```

The script installs the apt packages, builds `rpi-rgb-led-matrix` at a pinned commit,
installs the fonts, sudoers rule and systemd services, and turns off onboard audio.
[`deploy/README.md`](deploy/README.md) lists what goes where.

## Hardware

- Raspberry Pi 4
- Two 64×32 HUB75 panels set up as a 64×64 display (`chain_length=2`, `parallel=2`, `gpio_slowdown=4`; see `Display` in `display_control/utils.py`)
- RGB matrix HAT/adapter and a 5 V supply big enough for the panels

## Home Assistant (Power Flow mode)

`power_display.py` reads two sensors from the HA REST API (`/api/states`) every 5 seconds and
calculates house consumption as `grid + solar`. It only reads data and never changes anything
in HA. Configure it in `display_control/.env` (copy it from `.env.example`; it is gitignored):

```
HA_URL=http://homeassistant.local:8123
HA_TOKEN=<long-lived access token>
HA_SOLAR_ENTITY=sensor.balkonkraftwerk_power
HA_GRID_ENTITY=sensor.main_power        # negative = feeding into the grid
```

## Previewing without hardware

`display_control/simulator.py` renders the modes with Pillow, no LED matrix needed. Run it on any machine
that has `numpy` and `Pillow`:

```bash
cd display_control && python3 simulator.py
# -> christmas_preview.png, christmas_animation.gif, power_preview.png
```

## Useful commands

```bash
sudo systemctl status traintime display-control-web
sudo journalctl -u traintime -f
sudo systemctl restart traintime
```

## Repository layout

```
display_control/     current LED display code (see display_control/README.md for details)
  christmas_display.py, power_display.py   display modes
  utils.py           Display class: matrix setup, fonts, icons, drawing
  web_control.py     Flask mode switcher (port 5000)
  simulator.py       renders previews on a normal computer
  fonts/             BDF fonts (installed to /usr/share/fonts/bdf)
deploy/              install.sh, systemd units, sudoers rule
pitraintime/, manage.py, display_control.py, crontab, db.sqlite3
                     legacy Django train-departure display (not used now; Django isn't installed)
```
