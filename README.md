# TrainTime

Software for a 64×64 RGB LED matrix on a Raspberry Pi. It has several animated display
modes, and you switch between them from a small web page on the Pi.

![Christmas mode](display_control/christmas_animation.gif)

## Display modes

| Mode | Script | What it shows |
|---|---|---|
| Christmas Snow | `christmas_display.py` | Clock with falling snow that piles up on the ground and roofs, melts slowly and gets cleared by a passing snowplow |
| Power Flow | `power_display.py` | Live solar / grid / house power from Home Assistant, with animated arrows showing where the power flows |

One mode runs at a time, as the systemd service `traintime.service`.

## Switching modes

Open **http://pidisplay.local:5000** (or the Pi's IP) and click a mode. You can also use the API:

```bash
curl http://pidisplay.local:5000/api/status
curl -X POST http://pidisplay.local:5000/api/switch/power      # or: christmas
```

To switch, the web UI (`web_control.py`, itself running as `display-control-web.service`) rewrites the
`ExecStart` line of `traintime.service` from `deploy/systemd/traintime.service` and restarts it. A sudoers
rule (`deploy/sudoers/display-control`) lets user `pi` run exactly those commands.

## Hardware

- Raspberry Pi 3, 4 or 5 running Raspberry Pi OS Bookworm (64-bit)
- Two 64×32 HUB75 panels on two parallel chains, giving 64×64 (`parallel=2`, `chain_length=2` in `Display` in `utils.py`)
- RGB matrix HAT/adapter that supports 2 parallel chains, and a 5 V supply big enough for the panels

**Pi 3:** works the same. The GPIO slowdown is picked by model (Pi 4/5 → 4, Pi 3 → 2). If you see
glitches or flicker, set `LED_GPIO_SLOWDOWN` in `.env`. Building the LED library during install takes a few
minutes longer.

## Install on a new Pi

As user `pi` on a fresh Raspberry Pi OS Bookworm:

```bash
sudo apt-get install -y git
git clone https://github.com/nicolasj92/TrainTime.git ~/workspace/TrainTime
~/workspace/TrainTime/deploy/install.sh
nano ~/workspace/TrainTime/display_control/.env     # see Configuration
sudo systemctl restart traintime
```

`deploy/install.sh` is safe to re-run. It:

1. installs apt packages from `deploy/apt-packages.txt` (Pillow, numpy, requests, Flask, python-dotenv, build tools). Everything runs on the system `python3`, with no venv.
2. builds [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) at a pinned commit in `~/workspace/rpi-rgb-led-matrix` and installs its Python bindings
3. copies `display_control/fonts/*.bdf` to `/usr/share/fonts/bdf`. The LED library drops root privileges to user `daemon` before fonts load, and that user can't read `/home/pi`.
4. sets `dtparam=audio=off` in `/boot/firmware/config.txt`, because onboard audio conflicts with the matrix (you then need to reboot)
5. creates `display_control/.env` from `.env.example`
6. installs the sudoers rule and both systemd services, then enables and starts them

The repo has to live at `/home/pi/workspace/TrainTime`, because the service files use that path.

## Configuration

Everything goes in `display_control/.env`, which is gitignored. The template is
[`display_control/.env.example`](display_control/.env.example):

| Variable | Used by | Meaning |
|---|---|---|
| `LED_GPIO_SLOWDOWN` | all modes | Empty = auto by Pi model. Raise it if the image glitches |
| `HA_URL` | Power Flow | e.g. `http://homeassistant.local:8123` |
| `HA_TOKEN` | Power Flow | Home Assistant long-lived access token |
| `HA_SOLAR_ENTITY` | Power Flow | Solar production sensor in W |
| `HA_GRID_ENTITY` | Power Flow | Grid power sensor in W (negative = feeding in) |

Power Flow polls `GET /api/states` every 5 s, only reads data, and calculates house consumption as
`grid + solar`. A token from a non-admin HA user is enough.

Animation tweaks (snowflake count, plow interval, melt rate) are constants at the top of `main()` in
`christmas_display.py`.

The clock uses the system timezone: `sudo timedatectl set-timezone Europe/Berlin`.

## Preview without hardware

`simulator.py` renders the modes with Pillow on any computer (it needs `numpy` and `Pillow`, not the LED library):

```bash
cd display_control && python3 simulator.py
# -> christmas_preview.png, christmas_animation.gif, power_preview.png
```

## Running manually / debugging

```bash
sudo systemctl stop traintime                       # free the matrix first
cd ~/workspace/TrainTime/display_control
sudo python3 christmas_display.py                   # or power_display.py, Ctrl+C to stop

sudo systemctl status traintime display-control-web
sudo journalctl -u traintime -f
```

| Problem | Fix |
|---|---|
| Flicker / glitches | Set `LED_GPIO_SLOWDOWN` higher in `.env`; make sure audio is off (`dtparam=audio=off`) and reboot |
| Wrong time on the clock | `sudo timedatectl set-timezone <Zone>` |
| Power Flow shows 0 W | Check `HA_*` in `.env`; `curl -H "Authorization: Bearer $HA_TOKEN" $HA_URL/api/states` |
| "already running" | Another copy is using the matrix: `sudo systemctl stop traintime` |

## Repository layout

```
display_control/
  christmas_display.py   Christmas Snow mode
  power_display.py       Power Flow mode (Home Assistant)
  utils.py               Display class: matrix setup, fonts, icons, drawing
  web_control.py         Flask mode switcher on :5000 (+ templates/control.html)
  simulator.py           renders previews on a normal computer
  fonts/                 BDF fonts (X.Org, see fonts/AUTHORS), installed to /usr/share/fonts/bdf
  .env.example           configuration template
deploy/
  install.sh             set up a fresh Pi
  apt-packages.txt       system packages
  systemd/               traintime.service, display-control-web.service
  sudoers/               display-control (lets the web UI restart the display)
```

The earlier Django train-departure display is kept at the git tag `legacy-django` and on the
`single_display` branch.
