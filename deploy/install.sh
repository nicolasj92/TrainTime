#!/usr/bin/env bash
# Set up a fresh Raspberry Pi OS (Bookworm) Pi as a TrainTime LED matrix display.
# Safe to re-run. Usage (as user pi):
#   git clone https://github.com/nicolasj92/TrainTime.git ~/workspace/TrainTime
#   ~/workspace/TrainTime/deploy/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY="$REPO_DIR/deploy"
WS="$(dirname "$REPO_DIR")"
LED_DIR="$WS/rpi-rgb-led-matrix"
LED_COMMIT="d10f518f291bd34ca4816ef25cadf2446b882662"   # version running on the original pidisplay

[[ "$REPO_DIR" == /home/pi/workspace/TrainTime ]] || \
  echo "WARNING: service files expect /home/pi/workspace/TrainTime (repo is at $REPO_DIR)"

echo "==> apt packages"
sudo apt-get update
sudo apt-get install -y $(grep -v '^#' "$DEPLOY/apt-packages.txt")

echo "==> rpi-rgb-led-matrix (lib + python bindings)"
[[ -d "$LED_DIR/.git" ]] || git clone https://github.com/hzeller/rpi-rgb-led-matrix.git "$LED_DIR"
git -C "$LED_DIR" fetch -q origin
git -C "$LED_DIR" checkout -q "$LED_COMMIT"
make -C "$LED_DIR" -j"$(nproc)"
make -C "$LED_DIR/bindings/python" build-python PYTHON=/usr/bin/python3
sudo make -C "$LED_DIR/bindings/python" install-python PYTHON=/usr/bin/python3

echo "==> BDF fonts -> /usr/share/fonts/bdf (must be readable after rgbmatrix drops root)"
sudo install -d -m 0755 /usr/share/fonts/bdf
sudo install -m 0644 "$REPO_DIR"/display_control/fonts/*.bdf /usr/share/fonts/bdf/

echo "==> disable onboard audio (conflicts with LED matrix timing)"
CFG=/boot/firmware/config.txt
if grep -q '^dtparam=audio=on' "$CFG"; then
  sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$CFG"; REBOOT=1
elif ! grep -q '^dtparam=audio=off' "$CFG"; then
  echo 'dtparam=audio=off' | sudo tee -a "$CFG" >/dev/null; REBOOT=1
fi

echo "==> .env"
if [[ ! -f "$REPO_DIR/display_control/.env" ]]; then
  cp "$REPO_DIR/display_control/.env.example" "$REPO_DIR/display_control/.env"
  echo "    created display_control/.env from example -- fill in HA_URL / HA_TOKEN etc."
fi

echo "==> sudoers (lets the web UI restart the display service)"
sudo install -m 0440 -o root -g root "$DEPLOY/sudoers/display-control" /etc/sudoers.d/display-control
sudo visudo -cf /etc/sudoers.d/display-control

echo "==> systemd services"
for s in traintime display-control-web; do
  sudo install -m 0644 "$DEPLOY/systemd/$s.service" /etc/systemd/system/$s.service
done
sudo systemctl daemon-reload
sudo systemctl enable --now traintime.service display-control-web.service

echo
echo "Done. Web control: http://$(hostname -I | awk '{print $1}'):5000"
[[ "${REBOOT:-0}" == 1 ]] && echo "Reboot required (audio setting changed): sudo reboot"
exit 0
