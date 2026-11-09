# LED Matrix Display Modes

Control software for a 64x64 LED matrix display with multiple display modes including Christmas snow animation and real-time power flow visualization.

## Features

### Christmas Display Mode
- Current time display with smooth animations
- Falling snowflakes with realistic physics (gravity, drift, accumulation)
- Snow accumulation at ground level (up to 10 pixels high)
- Periodic snowplow that clears accumulated snow
- Gradual snow melting effect
- Smooth sub-pixel rendering for natural-looking animations

### Power Flow Display Mode
- Real-time energy monitoring from Home Assistant
- Visual representation of solar power generation
- Grid power consumption/export tracking
- Home power usage calculation
- Animated power flow indicators

## Hardware Requirements

- Raspberry Pi (tested on Pi 4)
- 64x64 RGB LED Matrix (2 panels: 64x32 each in chain configuration)
- Adafruit RGB Matrix HAT or equivalent
- 5V power supply (adequate for LED matrix)

## Software Prerequisites

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
sudo apt-get install -y python3-pip python3-dev git

# Install RGB Matrix library
cd ~
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd rpi-rgb-led-matrix
make build-python PYTHON=$(which python3)
sudo make install-python PYTHON=$(which python3)

# Install BDF fonts
sudo apt-get install -y xfonts-base
```

## Installation

1. Clone or copy the repository to your Raspberry Pi:

```bash
cd /home/pi/workspace
git clone <your-repo-url> TrainTime
cd TrainTime/display_control
```

2. Install Python dependencies:

```bash
pip3 install python-dotenv requests numpy flask
```

3. Install and enable the web control interface:

```bash
cd /home/pi/workspace/TrainTime/display_control

# The service files are already included, just install them
sudo cp /tmp/display-control-web.service /etc/systemd/system/
sudo cp /tmp/display-control-sudo /etc/sudoers.d/display-control
sudo chmod 0440 /etc/sudoers.d/display-control
sudo systemctl daemon-reload
sudo systemctl enable display-control-web.service
sudo systemctl start display-control-web.service
```

4. Set the correct timezone:

```bash
# For Central European Time (GMT+1)
sudo timedatectl set-timezone Europe/Berlin

# Verify timezone
timedatectl
```

5. Configure environment variables (for Power Display mode):

```bash
# Create .env file in display_control directory
nano .env
```

Add the following:
```
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_home_assistant_long_lived_token
HA_SOLAR_ENTITY=sensor.your_solar_power_sensor
HA_GRID_ENTITY=sensor.your_grid_power_sensor
```

## Running Display Modes

### Web Interface (Recommended)

A web control panel is available to easily switch between display modes.

**Access the web interface:**
```
http://192.168.178.97:5000
```
Or use your Pi's hostname:
```
http://pidisplay.local:5000
```

The web interface shows:
- Current display mode
- Service status
- One-click switching between modes

The web control service runs automatically on boot.

**Manage the web interface:**
```bash
# Check status
sudo systemctl status display-control-web.service

# Restart the web interface
sudo systemctl restart display-control-web.service

# View logs
sudo journalctl -u display-control-web.service -f
```

### Manual Execution

**Christmas Display:**
```bash
cd /home/pi/workspace/TrainTime/display_control
sudo FONT_DIR=/usr/share/fonts/bdf python3 christmas_display.py
```

**Power Flow Display:**
```bash
cd /home/pi/workspace/TrainTime/display_control
sudo FONT_DIR=/usr/share/fonts/bdf python3 power_display.py
```

Press `Ctrl+C` to stop any running display.

### Automatic Start on Boot (systemd service)

The display runs as a systemd service that starts automatically on boot.

#### Check Current Service Status

```bash
sudo systemctl status traintime.service
```

#### Switch Between Display Modes (Command Line)

**Method 1: Use the web interface (see above) - Easiest!**

**Method 2: Edit the service file directly**

```bash
# Edit the service file
sudo nano /etc/systemd/system/traintime.service
```

Change the `ExecStart` line to your desired mode:
- For Christmas: `ExecStart=/usr/bin/python3 christmas_display.py`
- For Power Flow: `ExecStart=/usr/bin/python3 power_display.py`

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart traintime.service
```

**Method 2: Quick switch using temporary file**

```bash
# Create new service config
cat > /tmp/traintime.service << 'EOF'
[Unit]
Description=Train Time Christmas Display
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/workspace/TrainTime/display_control
Environment=FONT_DIR=/usr/share/fonts/bdf
ExecStart=/usr/bin/python3 christmas_display.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Copy to system location and restart
sudo cp /tmp/traintime.service /etc/systemd/system/traintime.service
sudo systemctl daemon-reload
sudo systemctl restart traintime.service
```

Replace `christmas_display.py` with `power_display.py` to switch to power mode.

#### Service Management Commands

```bash
# Start the service
sudo systemctl start traintime.service

# Stop the service
sudo systemctl stop traintime.service

# Restart the service
sudo systemctl restart traintime.service

# Enable auto-start on boot
sudo systemctl enable traintime.service

# Disable auto-start on boot
sudo systemctl disable traintime.service

# View service logs
sudo journalctl -u traintime.service -f
```

## Configuration

### Christmas Display Settings

Edit `christmas_display.py` to customize:

- **Number of snowflakes**: Change `num_snowflakes = 30` (line 67)
- **Snowfall speed**: Modify speeds in `Snowflake.__init__()` (line 30)
- **Snowplow frequency**: Adjust `frames_until_plow` range (line 76)
- **Snow melting rate**: Change melting interval (line 158)
- **Max snow height**: Modify limit in accumulation logic (line 116)

### Power Display Settings

Edit `.env` file to configure Home Assistant integration:
- Update entity IDs to match your Home Assistant sensors
- Adjust update interval in `update_power_values()` (line 78)

## File Structure

```
TrainTime/display_control/
├── README.md                  # This file
├── christmas_display.py       # Christmas snow animation mode
├── power_display.py          # Power flow visualization mode
├── utils.py                  # Shared display utilities and icon classes
├── .env                      # Environment variables (create manually)
└── fonts/                    # BDF font files
    ├── 4x6.bdf              # Small font
    ├── 5x7.bdf              # Large font (used for time)
    └── README.md
```

## Troubleshooting

### Display shows wrong time
```bash
# Check timezone
timedatectl

# Set correct timezone (example for CET)
sudo timedatectl set-timezone Europe/Berlin
```

### Service won't start
```bash
# Check for errors
sudo journalctl -u traintime.service -n 50

# Verify file permissions
ls -la /home/pi/workspace/TrainTime/display_control/*.py

# Make scripts executable
chmod +x /home/pi/workspace/TrainTime/display_control/*.py
```

### Multiple instances running
```bash
# The scripts include locking to prevent multiple instances
# If you see "already running" message, stop the service first:
sudo systemctl stop traintime.service
```

### Home Assistant connection fails
```bash
# Verify .env file exists and has correct values
cat /home/pi/workspace/TrainTime/display_control/.env

# Test connection manually
curl -H "Authorization: Bearer YOUR_TOKEN" http://homeassistant.local:8123/api/states
```

### Matrix display issues
```bash
# If you see flickering or performance issues, add to /boot/cmdline.txt:
isolcpus=3

# Then reboot
sudo reboot
```

## Customization Ideas

### Christmas Display
- Adjust snowflake drift patterns for wind effects
- Modify snowplow design in `utils.py` `print_christmas()` method
- Change snow color tint (currently blue-tinted white)
- Add stars or other decorative elements
- Modify time display position or font

### Power Display
- Add battery status if you have energy storage
- Customize flow animation speed
- Change color schemes for different power sources
- Add alerts for high consumption

## Performance Notes

- The display runs at approximately 20 FPS for smooth animations
- Christmas mode uses sub-pixel rendering for smooth snowflake movement
- Both modes use double-buffering with VSync for flicker-free display
- Services auto-restart if they crash (configured in systemd)

## Credits

- Built using [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) library by Henner Zeller
- BDF fonts from X.Org Foundation

## License

See main repository for license information.
