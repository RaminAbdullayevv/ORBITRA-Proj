"""Run one built-site HTTP/WebSocket smoke against a disposable copy of the Main DB."""
import json
import sqlite3
import os
import subprocess
import sys
import time
from pathlib import Path
import httpx
from websockets.sync.client import connect

root = Path(__file__).resolve().parents[1]
source = sqlite3.connect(root / 'orbitra.db')
target = sqlite3.connect(root / 'orbitra-smoke.db')
try: source.backup(target)
finally: source.close(); target.close()
admin_password = os.environ['ORBITRA_TEST_ADMIN_PASSWORD']
virtual_password = os.environ['ORBITRA_TEST_VIRTUAL_PASSWORD']
origin = 'http://127.0.0.1:8011'
base = origin
env = os.environ.copy()
env.update(DATABASE_URL='sqlite:///./orbitra-smoke.db', FRONTEND_ORIGIN=origin)
flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8011'],
                          cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          creationflags=flags)
try:
    for _ in range(60):
        if server.poll() is not None: raise RuntimeError('Backend exited during startup')
        try:
            if httpx.get(base + '/api/v1/health', timeout=1, trust_env=False).status_code == 200: break
        except httpx.HTTPError: pass
        time.sleep(.25)
    else: raise RuntimeError('Backend did not become ready')
    with httpx.Client(base_url=base, timeout=5, trust_env=False) as a, httpx.Client(base_url=base, timeout=5, trust_env=False) as v:
        assert a.get('/login').status_code == 200
        ar = a.post('/api/v1/auth/login', json={'username':'admin','password':admin_password}, headers={'Origin':origin})
        vr = v.post('/api/v1/auth/login', json={'username':'virtual','password':virtual_password}, headers={'Origin':origin})
        assert ar.status_code == vr.status_code == 200, (ar.text, vr.text)
        assert a.get('/mission-control').status_code == 200 and a.get('/virtual-device').status_code == 403
        assert v.get('/virtual-device').status_code == 200 and v.get('/mission-control').status_code == 403
        assert v.get('/api/v1/security/overview').status_code == 403
        ah = {'Origin':origin,'X-CSRF-Token':ar.json()['csrf_token']}
        vh = {'Origin':origin,'X-CSRF-Token':vr.json()['csrf_token']}
        assert a.post('/api/v1/virtual-device/start', headers=ah).status_code == 403
        start = v.post('/api/v1/virtual-device/start', headers=vh, json={'scenario':'NORMAL_MISSION'})
        assert start.status_code == 200, start.text
        time.sleep(2)
        device = v.get('/api/v1/virtual-device/state').json()['device']
        monitor = a.get('/api/v1/telemetry/state').json()
        assert device['sensors']['temperature_1_c'] == monitor['latest_sample']['sensors']['temperature_1_c']
        cookie = 'orbitra_session=' + a.cookies.get('orbitra_session')
        with connect('ws://127.0.0.1:8011/api/v1/telemetry/ws', origin=origin,
                     additional_headers={'Cookie':cookie}, open_timeout=5, close_timeout=2) as ws:
            frame = json.loads(ws.recv(timeout=5))
            assert frame['latest_sample']['sensors']['temperature_1_c'] == device['sensors']['temperature_1_c']
        assert v.post('/api/v1/virtual-device/pause', headers=vh).status_code == 200
        assert a.get('/api/v1/telemetry/state').json()['device']['status'] == 'PAUSED'
        assert v.post('/api/v1/virtual-device/resume', headers=vh).status_code == 200
        assert v.post('/api/v1/virtual-device/reset', headers=vh).status_code == 200
        invalid = v.post('/api/v1/virtual-device/start', headers=vh, json={'scenario':'INVALID_SIGNATURE'})
        assert invalid.status_code == 200, invalid.text
        run = invalid.json()['run_id']
        time.sleep(11)
        state = a.get('/api/v1/telemetry/state').json()
        assert 'INTEGRITY_REJECTED' in [r['reason_code'] for r in state['rejections']]
        samples = a.get('/api/v1/telemetry/runs/' + run + '/samples').json()['samples']
        assert 10 not in [r['sequence_number'] for r in samples]
        incidents = a.get('/api/v1/security/overview').json()['incidents']
        assert 'INTEGRITY_REJECTED' in [r['reason_code'] for r in incidents]
        assert v.post('/api/v1/auth/logout', headers=vh).status_code == 204
        assert v.get('/api/v1/virtual-device/state').status_code == 401
        assert a.post('/api/v1/auth/logout', headers=ah).status_code == 204
        assert a.get('/api/v1/telemetry/state').status_code == 401
        print('ONE_ORIGIN_HTTP_WS_ROLES_TELEMETRY_REJECTION_LOGOUT_OK')
finally:
    server.terminate()
    try: server.wait(timeout=5)
    except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
    for _ in range(20):
        try:
            (root / 'orbitra-smoke.db').unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(.25)
