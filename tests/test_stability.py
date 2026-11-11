"""Stability regression checks for the v0.3.2 Windows 11 fix."""
from __future__ import annotations
import asyncio
import time
from fastapi.testclient import TestClient
from app.main import create_app
from core.runtime import SocketHub


def test_stalled_websocket_cannot_block_player_update(tmp_path):
    app = create_app(tmp_path / 'app.sqlite3')
    class BlockedClient:
        async def send_json(self, data):
            await asyncio.sleep(60)
    blocked = BlockedClient()
    with TestClient(app) as client:
        # Simulate a native WebView2 websocket that stopped reading data.
        app.state.runtime.hub.connections[blocked] = 'admin'
        started = time.monotonic()
        first = client.post('/api/players', json={'nickname':'ALPHA','seat':1})
        assert first.status_code == 200, first.text
        assert time.monotonic()-started < 3.0
        assert blocked not in app.state.runtime.hub.connections
        for i in range(2, 11):
            result = client.post('/api/players', json={'nickname':f'PLAYER {i}', 'seat':i})
            assert result.status_code == 200, result.text
        assert len(client.get('/api/state').json()['players']) == 10


def test_ui_diagnostics_accept_heartbeat_without_private_data(tmp_path):
    app = create_app(tmp_path / 'app.sqlite3')
    with TestClient(app) as client:
        assert client.post('/api/desktop/heartbeat', json={'page':'/admin'}).json()['ok']
        assert app.state.ui_heartbeat_time > 0
        assert app.state.ui_heartbeat_page == '/admin'
        assert client.post('/api/desktop/client-error', json={'kind':'error','message':'JS test'}).json()['ok']
        assert client.post('/api/desktop/heartbeat', json={'page':'X'*600}).status_code == 413
        assert client.post('/api/desktop/heartbeat', json={'page':'X'*100}).status_code == 200
        assert len(app.state.ui_heartbeat_page) <= 40


def test_native_safe_mode_and_valid_modules_structure():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    assert '--safe-mode' in (root/'launcher.py').read_text(encoding='utf8')
    assert 'START_SAFE_MODE.cmd' in (root/'scripts/BUILD_WINDOWS11.ps1').read_text(encoding='utf-8-sig')
    assert (root/'modules/hj_players/migrations').exists()


def test_multiple_stalled_websockets_do_not_accumulate_delays(tmp_path):
    app = create_app(tmp_path / 'app.sqlite3')

    class BlockedClient:
        async def send_json(self, data):
            await asyncio.sleep(60)

    blocked = [BlockedClient() for _ in range(6)]
    with TestClient(app) as client:
        for ws in blocked:
            app.state.runtime.hub.connections[ws] = 'overlay'
        started = time.monotonic()
        response = client.post('/api/players', json={'nickname': 'NO DELAY', 'seat': 1})
        assert response.status_code == 200, response.text
        assert time.monotonic() - started < 3.0
        assert all(ws not in app.state.runtime.hub.connections for ws in blocked)
