#!/usr/bin/env python3
"""
Web Control Interface for LED Matrix Display
Simple Flask app to switch between display modes
"""

from flask import Flask, render_template, redirect, url_for, jsonify
import subprocess
import os
import re

app = Flask(__name__)

DISPLAY_MODES = {
    'christmas': {
        'name': 'Christmas Snow',
        'description': 'Falling snow with time display',
        'script': 'christmas_display.py'
    },
    'power': {
        'name': 'Power Flow',
        'description': 'Real-time energy monitoring',
        'script': 'power_display.py'
    },
    'departures': {
        'name': 'Departures',
        'description': 'Next buses and trams (RMV)',
        'script': 'departures_display.py'
    }
}

SERVICE_FILE = '/etc/systemd/system/traintime.service'
SERVICE_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'deploy', 'systemd', 'traintime.service')


def get_current_mode():
    """Read the current mode from the service file"""
    try:
        with open(SERVICE_FILE, 'r') as f:
            content = f.read()
            for mode, info in DISPLAY_MODES.items():
                if info['script'] in content:
                    return mode
        return 'unknown'
    except Exception as e:
        print(f"Error reading service file: {e}")
        return 'unknown'


def get_service_status():
    """Get the current status of the traintime service"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'traintime.service'],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Error checking service status: {e}")
        return 'unknown'


def switch_mode(mode):
    """Switch to a different display mode"""
    if mode not in DISPLAY_MODES:
        return False, "Invalid mode"

    script = DISPLAY_MODES[mode]['script']

    try:
        # Same unit file install.sh uses, with only the ExecStart script swapped
        with open(SERVICE_TEMPLATE) as f:
            service_config = re.sub(r'^ExecStart=.*$', f'ExecStart=/usr/bin/python3 {script}',
                                    f.read(), flags=re.M)

        # Write to temporary file
        temp_file = '/tmp/traintime.service'
        with open(temp_file, 'w') as f:
            f.write(service_config)

        # Copy to system location and restart
        subprocess.run(['sudo', 'cp', temp_file, SERVICE_FILE], check=True)
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        subprocess.run(['sudo', 'systemctl', 'restart', 'traintime.service'], check=True)

        return True, f"Switched to {DISPLAY_MODES[mode]['name']} mode"
    except subprocess.CalledProcessError as e:
        return False, f"Error switching mode: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


@app.route('/')
def index():
    """Main page showing current mode and available modes"""
    current_mode = get_current_mode()
    service_status = get_service_status()

    return render_template(
        'control.html',
        current_mode=current_mode,
        service_status=service_status,
        modes=DISPLAY_MODES
    )


@app.route('/switch/<mode>')
def switch(mode):
    """Switch to a different mode"""
    success, message = switch_mode(mode)
    if success:
        return redirect(url_for('index'))
    else:
        return f"Error: {message}", 500


@app.route('/api/status')
def api_status():
    """API endpoint for current status"""
    return jsonify({
        'current_mode': get_current_mode(),
        'service_status': get_service_status(),
        'modes': DISPLAY_MODES
    })


@app.route('/api/switch/<mode>', methods=['POST'])
def api_switch(mode):
    """API endpoint to switch modes"""
    success, message = switch_mode(mode)
    return jsonify({
        'success': success,
        'message': message,
        'current_mode': get_current_mode() if success else None
    })


if __name__ == '__main__':
    # Run on all interfaces, port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
