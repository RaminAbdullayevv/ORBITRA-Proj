"""Local Vite proxy and WebSocket smoke using a disposable database copy."""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
import httpx
from websockets.sync.client import connect

backend = Path(__file__).resolve().parents[1]
frontend = backend.parent / 'frontend'
original = sqlite3.connect(backend / 'orbitra.db')
copy = sqlite3.connect(backend / 'orbitra-smoke.db')
try: original.backup(copy)
finally: original.close(); copy.close()
origin = 'http://localhost:5175'
env = os.environ.copy()
env.update(DATABASE_URL='sqlite:///./orbitra-smoke.db', FRONTEND_ORIGIN=origin,
           ORBITRA_API_PROXY_TARGET='http://127.0.0.1:8012')
flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
backend_proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8012'],
    cwd=backend, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
vite_proc = subprocess.Popen(['node', str(frontend / 'node_modules/vite/bin/vite.js'), '--host', 'localhost', '--port', '5175', '--strictPort'],
    cwd=frontend, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
try:
    with httpx.Client(base_url=origin, timeout=4, trust_env=False) as virtual, httpx.Client(base_url=origin, timeout=4, trust_env=False) as admin:
        for _ in range(80):
            if backend_proc.poll() is not None or vite_proc.poll() is not None: raise RuntimeError('server exited')
            try:
                if virtual.get('/login').status_code == 200 and virtual.get('/api/v1/health').status_code == 200: break
            except httpx.HTTPError: pass
            time.sleep(.25)
        else: raise RuntimeError('Vite proxy did not become ready')
        v = virtual.post('/api/v1/auth/login', json={'username':'virtual','password':os.environ['ORBITRA_TEST_VIRTUAL_PASSWORD']}, headers={'Origin':origin})
        a = admin.post('/api/v1/auth/login', json={'username':'admin','password':os.environ['ORBITRA_TEST_ADMIN_PASSWORD']}, headers={'Origin':origin})
        assert v.status_code == a.status_code == 200, (v.text, a.text)
        vh={'Origin':origin,'X-CSRF-Token':v.json()['csrf_token']}
        start=virtual.post('/api/v1/virtual-device/start',json={'scenario':'NORMAL_MISSION'},headers=vh)
        assert start.status_code == 200,start.text
        time.sleep(2)
        device=virtual.get('/api/v1/virtual-device/state').json()['device']
        monitor=admin.get('/api/v1/telemetry/state').json()
        assert device['sensors']['temperature_1_c']==monitor['latest_sample']['sensors']['temperature_1_c']
        cookie='orbitra_session='+admin.cookies.get('orbitra_session')
        with connect('ws://localhost:5175/api/v1/telemetry/ws',origin=origin,additional_headers={'Cookie':cookie},open_timeout=5,close_timeout=2) as ws:
            assert json.loads(ws.recv(timeout=5))['type']=='simulation_status'
        print('VITE_PROXY_HTTP_LOGIN_WS_SHARED_TEMPERATURE_OK')
finally:
    for process in (vite_proc, backend_proc):
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    for _ in range(20):
        try:
            (backend / 'orbitra-smoke.db').unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(.25)
