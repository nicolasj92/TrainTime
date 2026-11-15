#!/usr/bin/env python3
"""
Web UI on port 5000 (runs as user pi via display-control-web.service):

  /            switch display mode
  /pictures    upload, crop, pick and order pictures for the Pictures mode
  /departures  RMV settings: key, station, directions, lines, walk time
  /wifi        add Wi-Fi networks; also the captive-portal page of the setup hotspot
  /system      version and software updates from GitHub releases, location, brightness

Settings are stored in display_control/.env; the display service is restarted to apply them.
"""

import io
import json
import re
import secrets
import socket
import subprocess
import threading
import time
from pathlib import Path

import requests
from dotenv import dotenv_values
from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from PIL import Image, ImageOps

import pictures as library

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / '.env'
VERSION_FILE = HERE.parent / 'VERSION'
UPDATE_STATE = Path('/run/pidisplay/update.json')
UPDATE_LOG = Path('/var/log/pidisplay-update.log')
HOTSPOT_STATE = Path('/run/pidisplay/hotspot.json')
SCAN_FILE = Path('/run/pidisplay/scan.json')
RMV_API = 'https://www.rmv.de/hapi'

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 40 * 1024 * 1024   # uploads

DISPLAY_MODES = {
    'christmas': {
        'name': 'Christmas Snow',
        'description': 'Falling snow with time display'
    },
    'power': {
        'name': 'Power Flow',
        'description': 'Real-time energy monitoring'
    },
    'departures': {
        'name': 'Departures',
        'description': 'Next buses and trams (RMV)'
    },
    'sky': {
        'name': 'Sky Clock',
        'description': 'Sun, moon, stars and the live weather over your location'
    },
    'picture': {
        'name': 'Pictures',
        'description': 'Your photos (slideshow)'
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
# traintime.service runs main.py, which starts <DISPLAY_MODE>_display.py

def get_current_mode():
    mode = env().get('DISPLAY_MODE')
    return mode if mode in DISPLAY_MODES else 'unknown'


def get_service_status():
    r = subprocess.run(['systemctl', 'is-active', 'traintime.service'], capture_output=True, text=True)
    return r.stdout.strip() or 'unknown'


def restart_display():
    subprocess.run(['sudo', 'systemctl', 'restart', 'traintime.service'], check=True)


def switch_mode(mode):
    if mode not in DISPLAY_MODES:
        return False, "Invalid mode"
    try:
        update_env({'DISPLAY_MODE': mode})
        restart_display()
        return True, f"Switched to {DISPLAY_MODES[mode]['name']} mode"
    except Exception as e:
        return False, f"Error switching mode: {e}"


_restart_timer = None


def restart_if_showing(mode):
    """Restart the display soon if it's showing `mode` (debounced: several quick edits, one restart)."""
    global _restart_timer
    if get_current_mode() != mode:
        return
    if _restart_timer:
        _restart_timer.cancel()
    _restart_timer = threading.Timer(1.5, lambda: subprocess.run(
        ['sudo', '-n', 'systemctl', 'restart', 'traintime.service']))
    _restart_timer.start()


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


# --- pictures ----------------------------------------------------------------------

def panel_size():
    return env().get('LED_PANEL') or '64x32'


@app.route('/pictures', methods=['GET', 'POST'])
def pictures_page():
    notice = None
    if request.method == 'POST':
        seconds = max(3, min(3600, int(float(request.form.get('seconds') or 20))))
        transition = request.form.get('transition')
        update_env({'PICTURE_SECONDS': str(seconds),
                    'PICTURE_TRANSITION': transition if transition in library.TRANSITIONS else 'slide'})
        restart_if_showing('picture')
        notice = 'Saved.'
    e = env()
    size = panel_size()
    return render_template('pictures.html', page='pictures', notice=notice, panel=size,
                           panel_w=int(size.split('x')[0]), panel_h=int(size.split('x')[1]),
                           pictures=library.load()['pictures'], showing=get_current_mode() == 'picture',
                           seconds=e.get('PICTURE_SECONDS') or '20',
                           transition=e.get('PICTURE_TRANSITION') or 'slide',
                           transitions=library.TRANSITIONS)


@app.route('/api/pictures', methods=['POST'])
def api_picture_upload():
    added = []
    for f in request.files.getlist('file'):
        try:
            img = ImageOps.exif_transpose(Image.open(f.stream))
            img.load()
        except Exception:
            return jsonify({'error': f'{f.filename}: not an image the Pi can read'}), 400
        added.append(library.add(img, f.filename or 'picture'))
    restart_if_showing('picture')
    return jsonify({'added': added})


@app.route('/api/pictures/<pid>', methods=['POST', 'DELETE'])
def api_picture(pid):
    if request.method == 'DELETE':
        ok = library.remove(pid)
    else:
        data = request.get_json(force=True)
        changes = {}
        if 'enabled' in data:
            changes['enabled'] = bool(data['enabled'])
        if 'crop' in data:
            crop = [float(v) for v in data['crop']]
            if len(crop) != 4 or not all(0 <= v <= 1 for v in crop):
                return jsonify({'error': 'bad crop'}), 400
            changes['crop'] = {panel_size(): crop}
        if 'move' in data:
            changes['move'] = int(data['move'])
        ok = library.update(pid, **changes)
    if not ok:
        return jsonify({'error': 'no such picture'}), 404
    restart_if_showing('picture')
    return jsonify({'pictures': library.load()['pictures']})


@app.route('/pictures/img/<pid>/<kind>')
def picture_file(pid, kind):
    path = library.file_for(pid, thumb=(kind == 'thumb'))
    if not path:
        abort(404)
    return send_file(path, max_age=3600)


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


# --- system: version and updates -----------------------------------------------------

def current_version():
    try:
        return VERSION_FILE.read_text().strip()
    except OSError:
        return 'unknown'


def _version_tuple(v):
    m = re.match(r'v?(\d+)\.(\d+)\.(\d+)$', v or '')
    return tuple(int(x) for x in m.groups()) if m else None


_latest = {'checked': 0, 'release': None, 'error': None}


def latest_release(force=False):
    """Newest GitHub release (cached for 30 minutes)."""
    if not force and time.time() - _latest['checked'] < 1800:
        return _latest
    e = env()
    headers = {'Accept': 'application/vnd.github+json'}
    if e.get('GITHUB_TOKEN'):
        headers['Authorization'] = f"Bearer {e['GITHUB_TOKEN']}"
    repo = e.get('GITHUB_REPO') or 'nicolasj92/TrainTime'
    try:
        r = requests.get(f'https://api.github.com/repos/{repo}/releases/latest', headers=headers, timeout=8)
        if r.status_code == 404:
            raise RuntimeError('no release found (private repository without GITHUB_TOKEN?)')
        r.raise_for_status()
        data = r.json()
        _latest.update(release={'tag': data['tag_name'], 'name': data.get('name') or data['tag_name'],
                                'notes': data.get('body') or '', 'date': (data.get('published_at') or '')[:10],
                                'url': data.get('html_url')}, error=None)
    except Exception as ex:
        _latest.update(error=str(ex))
    _latest['checked'] = time.time()
    return _latest


def update_available():
    rel = _latest.get('release')
    new, cur = _version_tuple(rel and rel['tag']), _version_tuple(current_version())
    return bool(new and (cur is None or new > cur))


def update_state():
    try:
        return json.loads(UPDATE_STATE.read_text())
    except (OSError, ValueError):
        return None


def _background_check():
    while True:
        latest_release(force=True)
        time.sleep(6 * 3600)


@app.context_processor
def nav_badges():
    return {'update_badge': update_available()}


@app.route('/system', methods=['GET', 'POST'])
def system():
    notice = None
    if request.method == 'POST':
        values = {}
        try:
            lat, lon = float(request.form['lat']), float(request.form['lon'])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                values.update(SKY_LAT=f'{lat:.4f}', SKY_LON=f'{lon:.4f}')
        except (KeyError, ValueError):
            pass
        values['SKY_PLACE'] = clean(request.form.get('place', ''))[:60]
        values['SKY_WEATHER'] = '1' if request.form.get('weather') else '0'
        values['LED_BRIGHTNESS'] = str(max(10, min(100, int(request.form.get('brightness') or 80))))
        if request.form.get('github_token', '').strip():
            values['GITHUB_TOKEN'] = clean(request.form['github_token'])
        update_env(values)
        restart_display()
        notice = 'Saved. The display restarted with the new settings.'
    latest = latest_release(force=request.args.get('check') == '1')
    e = env()
    return render_template('system.html', page='system', notice=notice, version=current_version(),
                           latest=latest, available=update_available(), state=update_state(),
                           lat=e.get('SKY_LAT') or '49.87', lon=e.get('SKY_LON') or '8.65',
                           place=e.get('SKY_PLACE') or '', weather=e.get('SKY_WEATHER') != '0',
                           brightness=e.get('LED_BRIGHTNESS') or '100', hostname=socket.gethostname(),
                           has_token=bool(e.get('GITHUB_TOKEN')),
                           reboot_required=Path('/run/pidisplay/reboot-required').exists())


@app.route('/api/update', methods=['POST'])
def api_update():
    r = subprocess.run(['sudo', '-n', 'systemctl', 'start', '--no-block', 'pidisplay-update.service'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return jsonify({'error': r.stderr.strip() or 'could not start the update'}), 500
    return jsonify({'started': True})


@app.route('/api/reboot', methods=['POST'])
def api_reboot():
    subprocess.Popen(['sudo', '-n', 'systemctl', 'reboot'])
    return jsonify({'rebooting': True})


@app.route('/api/update/status')
def api_update_status():
    try:
        log = UPDATE_LOG.read_text().splitlines()[-12:]
    except OSError:
        log = []
    return jsonify({'state': update_state(), 'version': current_version(), 'log': log})


@app.route('/api/geocode')
def api_geocode():
    """Place search for the Sky Clock location (Open-Meteo geocoding, no key)."""
    try:
        r = requests.get('https://geocoding-api.open-meteo.com/v1/search',
                         params={'name': request.args.get('q', ''), 'count': 6, 'language': 'de'}, timeout=8)
        return jsonify([{'name': ', '.join(x for x in (p.get('name'), p.get('admin1'), p.get('country')) if x),
                         'lat': p['latitude'], 'lon': p['longitude']} for p in r.json().get('results', [])])
    except Exception as ex:
        return jsonify({'error': str(ex)}), 502


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
    threading.Thread(target=_background_check, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
