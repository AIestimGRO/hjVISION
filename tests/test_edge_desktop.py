"""Fast regression tests for the stable Windows Edge application window."""
import os
import json
import threading
import time
import urllib.request
from pathlib import Path
from unittest.mock import Mock

import launcher


def test_find_edge_executable_uses_windows_program_files(tmp_path, monkeypatch):
    program_files = tmp_path / 'Program Files (x86)'
    edge = program_files / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b'test')
    monkeypatch.setenv('PROGRAMFILES(X86)', str(program_files))
    monkeypatch.delenv('PROGRAMFILES', raising=False)
    monkeypatch.delenv('LOCALAPPDATA', raising=False)
    monkeypatch.setattr(launcher.shutil, 'which', lambda _: None)
    assert launcher.find_edge_executable() == edge.resolve()


def test_default_launcher_uses_edge_app_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, 'user_data_directory', lambda _staging: tmp_path)
    monkeypatch.setattr(launcher, 'prepare_logging', lambda _: tmp_path/'launcher.log')
    events=[]
    monkeypatch.setattr(launcher, 'run_edge_desktop', lambda staging: events.append(('edge',staging)))
    monkeypatch.setattr(launcher, 'run_desktop', lambda staging, safe_mode: events.append(('legacy',staging,safe_mode)))
    monkeypatch.setattr(launcher.sys, 'argv', ['HiJackLive.exe'])
    assert launcher.main() == 0
    assert events == [('edge', False)]


def test_edge_mode_serves_health_and_closes_server(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, 'user_data_directory', lambda _staging: tmp_path/'prod')
    edge=tmp_path/'msedge.exe'
    edge.write_bytes(b'test')
    monkeypatch.setattr(launcher,'find_edge_executable',lambda:edge)
    results={}

    # Simulate real Windows Edge: starter PID exits immediately, but the real
    # application window remains open and can still reach our local HTTP server.
    class FakeBrowser:
        pid=4242
        returncode=0
        def __init__(self, args, **kwargs):
            results['args']=args
            def verify_running_then_close():
                time.sleep(0.4)
                with urllib.request.urlopen('http://127.0.0.1:8766/health',timeout=4) as res:
                    results['health']=res.status
                with urllib.request.urlopen('http://127.0.0.1:8766/api/desktop/edge-session',timeout=4) as res:
                    token=json.load(res)['quit_token']
                request=urllib.request.Request('http://127.0.0.1:8766/api/desktop/edge-quit',
                        data=b'', method='POST',headers={'X-HJ-Desktop-Token':token})
                with urllib.request.urlopen(request,timeout=4) as res:
                    results['quit']=json.load(res)
            results['worker']=threading.Thread(target=verify_running_then_close,daemon=True)
            results['worker'].start()
        def poll(self):return self.returncode
        def terminate(self):raise AssertionError('browser already closed')

    monkeypatch.setattr(launcher, 'edge_profile_process_active', lambda _:False)
    monkeypatch.setattr(launcher.subprocess,'Popen',FakeBrowser)
    launcher.run_edge_desktop(staging=True)
    results['worker'].join(timeout=2)
    assert results['health'] == 200
    assert results['quit'] == {'ok': True}
    assert any(arg.startswith('--app=http://127.0.0.1:8766/admin') for arg in results['args'])
    assert any(arg.startswith('--user-data-dir=') for arg in results['args'])
    assert not any('--disable-gpu' in arg for arg in results['args'])
    assert not launcher.port_is_busy('127.0.0.1',8766)


def test_edge_session_lifetime_ignores_starter_process_exit():
    # An active browser profile OR a recent panel heartbeat must keep the
    # localhost server available even when the Popen starter PID has exited.
    assert not launcher.edge_session_should_exit(100, 80, 0, True)
    assert not launcher.edge_session_should_exit(100, 80, 99, False)
    assert not launcher.edge_session_should_exit(100, 80, 0, False)
    assert launcher.edge_session_should_exit(111, 80, 0, False)
    assert launcher.edge_session_should_exit(300, 80, 100, False)


def test_edge_quit_api_rejects_unauthenticated_requests(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app=create_app(tmp_path/'edge.sqlite3')
    event=threading.Event()
    launcher.configure_edge_control_routes(app,event)
    with TestClient(app, base_url='http://127.0.0.1:8766', client=('127.0.0.1',50000)) as client:
        assert client.post('/api/desktop/edge-quit').status_code == 403
        token=client.get('/api/desktop/edge-session').json()['quit_token']
        assert not event.is_set()
        assert client.post('/api/desktop/edge-quit',headers={
            'X-HJ-Desktop-Token':token,'Origin':'https://attacker.test'}).status_code == 403
        assert not event.is_set()
        assert client.post('/api/desktop/edge-quit',headers={
            'X-HJ-Desktop-Token':token}).json() == {'ok':True}
        assert event.is_set()


def test_edge_profile_probe_detects_handed_off_process(tmp_path, monkeypatch):
    import psutil
    class FakeProcess:
        def __init__(self, name, cmdline):
            self.info={'name':name,'cmdline':cmdline}
    profile = tmp_path/'edge-control-profile'
    monkeypatch.setattr(psutil,'process_iter',lambda fields: [
        FakeProcess('chrome.exe',['chrome.exe','--user-data-dir='+str(profile)]),
        FakeProcess('msedge.exe',['msedge.exe','--user-data-dir='+str(profile)])])
    assert launcher.edge_profile_process_active(profile)
    assert not launcher.edge_profile_process_active(tmp_path/'other-profile')
