#!/usr/bin/env python3
"""
Web UI on port 5000 (runs as user pi via display-control-web.service):

  /            switch display mode
  /departures  RMV settings: key, station, directions, lines, walk time
  /wifi        add Wi-Fi networks; also the captive-portal page of the setup hotspot

Settings are stored in display_control/.env; the display service is restarted to apply them.
"""

import json
import os
import re
import socket
import subprocess
from pathlib import Path

import requests
from dotenv import dotenv_values
from flask import Flask, jsonify, redirect, render_template, request, url_for

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / '.env'
SERVICE_FILE = '/etc/systemd/system/traintime.service'
SERVICE_TEMPLATE = HERE.parent / 'deploy' / 'systemd' / 'traintime.service'
HOTSPOT_STATE = Path('/run/pidisplay/hotspot.json')
SCAN_FILE = Path('/run/pidisplay/scan.json')
RMV_API = 'https://www.rmv.de/hapi'

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


# --- .env helpers ------------------------------------------------------------------

def env():
    return {k: (v or '') for k, v in dotenv_values(ENV_FILE).items()} if ENV_FILE.exists() else {}


def update_env(values):
    """Set keys in .env, keeping comments, order and all other settings."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    remaining = dict(values)
    for i, line in enumerate(lines):
        key = line.split('=', 1)[0].strip()
        if '=' in line and not line.lstrip().startswith('#') and key in remaining:
            lines[i] = f'{key}={remaining.pop(key)}'
    lines += [f'{k}={v}' for k, v in remaining.items()]
    tmp = ENV_FILE.with_suffix('.tmp')
    tmp.write_text('\n'.join(lines) + '\n')
    tmp.chmod(0o600)
    tmp.replace(ENV_FILE)


def clean(value):
    """Keep .env values on one line and free of quotes."""
    return re.sub(r'[\r\n"\'#]', '', str(value)).strip()


# --- display service ---------------------------------------------------------------

def get_current_mode():
    try:
        content = Path(SERVICE_FILE).read_text()
        for mode, info in DISPLAY_MODES.items():
            if info['script'] in content:
                return mode
    except OSError as e:
        print(f"Error reading service file: {e}")
    return 'unknown'


def get_service_status():
    r = subprocess.run(['systemctl', 'is-active', 'traintime.service'], capture_output=True, text=True)
    return r.stdout.strip() or 'unknown'


def restart_display():
    subprocess.run(['sudo', 'systemctl', 'restart', 'traintime.service'], check=True)


def switch_mode(mode):
    if mode not in DISPLAY_MODES:
        return False, "Invalid mode"
    script = DISPLAY_MODES[mode]['script']
    try:
        # Same unit file install.sh uses, with only the ExecStart script swapped
        service_config = re.sub(r'^ExecStart=.*$', f'ExecStart=/usr/bin/python3 {script}',
                                SERVICE_TEMPLATE.read_text(), flags=re.M)
        temp_file = '/tmp/traintime.service'
        with open(temp_file, 'w') as f:
            f.write(service_config)
        subprocess.run(['sudo', 'cp', temp_file, SERVICE_FILE], check=True)
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        restart_display()
        return True, f"Switched to {DISPLAY_MODES[mode]['name']} mode"
    except Exception as e:
        return False, f"Error switching mode: {e}"


# --- captive portal ----------------------------------------------------------------

def hotspot():
    try:
        return json.loads(HOTSPOT_STATE.read_text())
    except (OSError, ValueError):
        return None


@app.before_request
def captive_portal():
    """While the setup hotspot is up, send every request for another host to the Wi-Fi page."""
    state = hotspot()
    if state and request.host.split(':')[0] != state['ip'] and not request.path.startswith('/wifi'):
        return redirect(f"http://{state['ip']}/wifi", code=302)


# --- modes -------------------------------------------------------------------------

@app.route('/')
def index():
    e = env()
    return render_template('control.html', page='modes', current_mode=get_current_mode(),
                           service_status=get_service_status(), modes=DISPLAY_MODES,
                           panel=e.get('LED_PANEL') or '64x32',
                           notice=request.args.get('msg'), notice_error=request.args.get('err'))


@app.route('/switch/<mode>')
def switch(mode):
    success, message = switch_mode(mode)
    return redirect(url_for('index', msg=None if success else message, err=None if success else 1))


@app.route('/api/status')
def api_status():
    return jsonify({'current_mode': get_current_mode(), 'service_status': get_service_status(),
                    'modes': DISPLAY_MODES, 'hotspot': bool(hotspot())})


@app.route('/api/switch/<mode>', methods=['POST'])
def api_switch(mode):
    success, message = switch_mode(mode)
    return jsonify({'success': success, 'message': message,
                    'current_mode': get_current_mode() if success else None})


# --- departures settings -----------------------------------------------------------

def parse_directions(value):
    return [{'id': d.split(':', 1)[0], 'label': d.split(':', 1)[1]}
            for d in value.split(',') if ':' in d]


def rmv(endpoint, **params):
    token = env().get('RMV_ACCESS_TOKEN')
    if not token:
        raise RuntimeError('Save an RMV API key first')
    data = requests.get(f'{RMV_API}/{endpoint}', params={'accessId': token, 'format': 'json', **params},
                        timeout=10).json()
    if 'errorCode' in data:
        raise RuntimeError(f"RMV: {data.get('errorText') or data['errorCode']}")
    return data


@app.route('/departures', methods=['GET', 'POST'])
def departures():
    notice = notice_error = None
    if request.method == 'POST':
        f = request.form
        ids, labels = f.getlist('dir_id'), f.getlist('dir_label')
        directions = ','.join(f'{clean(i)}:{clean(l)[:8] or clean(i)}'
                              for i, l in zip(ids, labels) if clean(i).isdigit())
        values = {
            'RMV_STATION_ID': clean(f.get('station_id', '')),
            'RMV_STATION_NAME': clean(f.get('station_name', '')),
            'RMV_DIRECTIONS': directions,
            'RMV_LINES': ','.join(clean(x) for x in f.getlist('lines') if clean(x)),
            'RMV_WALK_MINUTES': str(max(0, min(60, int(f.get('walk') or 0)))),
        }
        if f.get('token', '').strip():
            values['RMV_ACCESS_TOKEN'] = clean(f['token'])
        update_env(values)
        try:
            restart_display()
            notice = 'Saved. The display restarted with the new settings.'
        except Exception as e:
            notice, notice_error = f'Saved, but restarting the display failed: {e}', True
    e = env()
    return render_template(
        'departures.html', page='departures', notice=notice, notice_error=notice_error,
        has_token=bool(e.get('RMV_ACCESS_TOKEN')),
        station_id=e.get('RMV_STATION_ID', '3004736'),
        station_name=e.get('RMV_STATION_NAME') or '',
        directions=parse_directions(e.get('RMV_DIRECTIONS', '3024730:Hbf,3004734:LiWi')),
        lines=[x for x in e.get('RMV_LINES', '').split(',') if x],
        walk=e.get('RMV_WALK_MINUTES') or '2')


@app.route('/api/rmv/stations')
def api_rmv_stations():
    try:
        data = rmv('location.name', input=request.args.get('q', ''), type='S', maxNo=8)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    stops = []
    for item in data.get('stopLocationOrCoordLocation', []):
        stop = item.get('StopLocation')
        if stop:
            stops.append({'id': stop.get('extId'), 'name': stop.get('name')})
    return jsonify(stops)


@app.route('/api/rmv/lines')
def api_rmv_lines():
    """Lines leaving the station in the next 3 hours (to fill the line filter)."""
    try:
        data = rmv('departureBoard', id=request.args.get('station', ''), duration=180, maxJourneys=60)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    lines = set()
    for dep in data.get('Departure', []):
        product = dep.get('Product')
        product = product[0] if isinstance(product, list) else (product or {})
        if product.get('line'):
            lines.add(product['line'].strip())
    return jsonify(sorted(lines, key=lambda s: (len(s), s)))


# --- Wi-Fi -------------------------------------------------------------------------

def setup_ssid():
    return (env().get('WIFI_SETUP_SSID') or f'{socket.gethostname()}-setup')[:32]


def visible_networks():
    """Networks seen in the last scan (the radio can't scan while it's the hotspot)."""
    if hotspot():
        try:
            return json.loads(SCAN_FILE.read_text())
        except (OSError, ValueError):
            return []
    out = subprocess.run(['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
                         capture_output=True, text=True).stdout
    nets = {}
    for line in out.splitlines():
        ssid, signal, security = (line.replace('\\:', '\0').split(':') + ['', '', ''])[:3]
        ssid = ssid.replace('\0', ':')
        if ssid and int(signal or 0) > nets.get(ssid, {}).get('signal', -1):
            nets[ssid] = {'ssid': ssid, 'signal': int(signal or 0), 'secure': bool(security.strip())}
    return sorted(nets.values(), key=lambda n: -n['signal'])


def saved_networks():
    out = subprocess.run(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                         capture_output=True, text=True).stdout
    return [line.rsplit(':', 1)[0] for line in out.splitlines()
            if line.endswith(':802-11-wireless') and not line.startswith('pidisplay-setup:')]


def current_network():
    out = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID', 'device', 'wifi'],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith('yes:'):
            return line[4:]
    return None


@app.route('/wifi', methods=['GET', 'POST'])
def wifi():
    state = hotspot()
    notice = notice_error = None
    if request.method == 'POST':
        payload = json.dumps({'ssid': request.form.get('ssid', ''),
                              'password': request.form.get('password', '')})
        r = subprocess.run(['sudo', '-n', '/usr/local/sbin/pidisplay-wifi'], input=payload,
                           capture_output=True, text=True)
        if r.returncode != 0:
            notice, notice_error = f"Couldn't save: {r.stderr.strip() or r.stdout.strip()}", True
        elif state:
            return render_template('wifi_connecting.html', page='wifi', ssid=request.form['ssid'],
                                   setup_ssid=state['ssid'])
        else:
            notice = f"Saved {request.form['ssid']}. The Pi prefers it whenever it's in range."
    return render_template('wifi.html', page='wifi', notice=notice, notice_error=notice_error,
                           hotspot=state, networks=visible_networks(), saved=saved_networks(),
                           current=None if state else current_network(), setup_ssid=setup_ssid())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
