#!/usr/bin/env bash
# Set up a fresh Raspberry Pi OS Trixie (or Bookworm) Pi as a TrainTime LED matrix display.
# Needs passwordless sudo for user pi (see README).
# Safe to re-run. Usage (as user pi):
#   git clone https://github.com/nicolasj92/TrainTime.git ~/workspace/TrainTime
#   ~/workspace/TrainTime/deploy/install.sh
# Optional: LED_PANEL=32x32 ~/workspace/TrainTime/deploy/install.sh   (sets the panel size in .env)
# Software updates (System page) re-run this script; steps that are already done are skipped.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY="$REPO_DIR/deploy"
WS="$(dirname "$REPO_DIR")"
LED_DIR="$WS/rpi-rgb-led-matrix"
LED_COMMIT="d10f518f291bd34ca4816ef25cadf2446b882662"   # version running on the original pidisplay

[[ "$REPO_DIR" == /home/pi/workspace/TrainTime ]] || \
  echo "WARNING: service files expect /home/pi/workspace/TrainTime (repo is at $REPO_DIR)"

echo "==> apt packages"
export DEBIAN_FRONTEND=noninteractive
PACKAGES=$(grep -v '^#' "$DEPLOY/apt-packages.txt")
MISSING=$(for p in $PACKAGES; do dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "ok installed" || echo "$p"; done)
if [[ -n "$MISSING" ]]; then
  sudo -E apt-get update
  sudo -E apt-get install -y $MISSING
else
  echo "    all installed"
fi

echo "==> rpi-rgb-led-matrix (lib + python bindings)"
STAMP="$LED_DIR/.pidisplay-built"
if [[ "$(cat "$STAMP" 2>/dev/null)" == "$LED_COMMIT" ]] && python3 -c 'import rgbmatrix' 2>/dev/null; then
  echo "    already built at ${LED_COMMIT:0:7}"
else
  [[ -d "$LED_DIR/.git" ]] || git clone https://github.com/hzeller/rpi-rgb-led-matrix.git "$LED_DIR"
  git -C "$LED_DIR" fetch -q origin
  git -C "$LED_DIR" checkout -q "$LED_COMMIT"
  make -C "$LED_DIR" -j"$(nproc)"
  make -C "$LED_DIR/bindings/python" build-python PYTHON=/usr/bin/python3
  sudo make -C "$LED_DIR/bindings/python" install-python PYTHON=/usr/bin/python3
  echo "$LED_COMMIT" > "$STAMP"
fi

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

# On Trixie the module still loads despite dtparam=audio=off, so blacklist it too
BLACKLIST=/etc/modprobe.d/blacklist-rgb-matrix.conf
if [[ ! -f "$BLACKLIST" ]]; then
  echo "blacklist snd_bcm2835" | sudo tee "$BLACKLIST" >/dev/null; REBOOT=1
fi

echo "==> keep CPU core 3 for the LED refresh (less flicker)"
CMDLINE=/boot/firmware/cmdline.txt
if ! grep -q 'isolcpus=3' "$CMDLINE"; then
  sudo sed -i '1 s/$/ isolcpus=3/' "$CMDLINE"; REBOOT=1
fi

echo "==> .env"
ENV="$REPO_DIR/display_control/.env"
if [[ ! -f "$ENV" ]]; then
  cp "$REPO_DIR/display_control/.env.example" "$ENV"
  echo "    created display_control/.env from example -- fill in HA_* / RMV_* as needed"
else
  # Older installs chose the mode by rewriting traintime.service; keep that mode
  OLD_UNIT=/etc/systemd/system/traintime.service
  if ! grep -q '^DISPLAY_MODE=' "$ENV" && [[ -f "$OLD_UNIT" ]]; then
    OLD_MODE=$(sed -n 's/^ExecStart=.* \([a-z]*\)_display\.py$/\1/p' "$OLD_UNIT")
    if [[ -n "$OLD_MODE" ]]; then echo "DISPLAY_MODE=$OLD_MODE" >> "$ENV"; echo "    kept display mode: $OLD_MODE"; fi
  fi
  # Append settings that were added to .env.example since this .env was created
  while IFS= read -r line; do
    key="${line%%=*}"
    if [[ "$line" =~ ^[A-Z_]+= ]] && ! grep -q "^$key=" "$ENV"; then
      echo "$line" >> "$ENV"; echo "    added $key to .env"
    fi
  done < "$REPO_DIR/display_control/.env.example"
fi

if [[ -n "${LED_PANEL:-}" ]]; then
  sed -i "s/^LED_PANEL=.*/LED_PANEL=$LED_PANEL/" "$ENV"
  echo "    panel size: $LED_PANEL"
fi

echo "==> sudoers (lets the web UI restart the display service)"
sudo install -m 0440 -o root -g root "$DEPLOY/sudoers/display-control" /etc/sudoers.d/display-control
sudo visudo -cf /etc/sudoers.d/display-control

echo "==> Wi-Fi fallback (setup hotspot when offline)"
sudo install -m 0755 -o root -g root "$DEPLOY/bin/wifi-fallback" /usr/local/sbin/pidisplay-wifi-fallback
sudo install -m 0755 -o root -g root "$DEPLOY/bin/pidisplay-wifi" /usr/local/sbin/pidisplay-wifi
sudo install -m 0755 -o root -g root "$DEPLOY/bin/pidisplay-update" /usr/local/sbin/pidisplay-update
sudo install -d /etc/NetworkManager/dnsmasq-shared.d
sudo install -m 0644 "$DEPLOY/networkmanager/pidisplay-portal.conf" /etc/NetworkManager/dnsmasq-shared.d/
if ! grep -q '^WIFI_SETUP_PASSWORD=.\{8,\}' "$ENV"; then
  # 8 chars without look-alikes (0/o, 1/l/i) so it's easy to read off the panel
  PW="$(python3 -c 'import secrets; print("".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8)))')"
  sed -i "s/^WIFI_SETUP_PASSWORD=.*/WIFI_SETUP_PASSWORD=$PW/" "$ENV"
  echo "    hotspot password: $PW (also shown on the display while the hotspot is up)"
fi

echo "==> systemd services"
for s in traintime display-control-web wifi-fallback pidisplay-update; do
  sudo install -m 0644 "$DEPLOY/systemd/$s.service" /etc/systemd/system/$s.service
done
sudo systemctl daemon-reload
sudo systemctl enable traintime.service display-control-web.service wifi-fallback.service
# (Re)start so new code and settings are used
sudo systemctl restart traintime.service display-control-web.service wifi-fallback.service

echo
echo "Done ($(cat "$REPO_DIR/VERSION")). Web control: http://$(hostname -I | awk '{print $1}'):5000"
if [[ "${REBOOT:-0}" == 1 ]]; then
  echo "Reboot required (boot settings changed): sudo reboot"
  sudo install -d /run/pidisplay && sudo touch /run/pidisplay/reboot-required
fi
exit 0
