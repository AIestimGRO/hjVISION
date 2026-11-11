"""Regression tests for the Windows launcher, executable preflight and clean shutdown.

The UI smoke uses a fake WebView window on Linux; native WebView2 is validated
only by the Windows EXE build's preflight and a manual launch on Windows 11.
"""
from __future__ import annotations
import sys
import types
import urllib.request
from pathlib import Path

import launcher


def test_external_modules_and_user_data_are_separate(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    mod = launcher.app_directory() / 'modules'
    assert (mod / 'hj_players' / 'module.json').exists()
    assert launcher.user_data_directory(False) == tmp_path/'HiJackLive'/'production'
    assert launcher.user_data_directory(True) == tmp_path/'HiJackLive'/'staging'


def test_headless_packaged_contract_preflight():
    launcher.self_test(launcher.app_directory() / 'modules')


def test_server_starts_in_desktop_and_stops_after_window_closes(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, 'user_data_directory', lambda staging: tmp_path/'test-data')
    created = {}

    class FakeWindow:
        def destroy(self):
            created['destroyed'] = True

    def create_window(title, url, **kwargs):
        created['title'] = title
        created['url'] = url
        created['opts'] = kwargs
        return FakeWindow()

    def start(**kwargs):
        created['gui'] = kwargs.get('gui')
        with urllib.request.urlopen(created['url'].replace('/admin', '/health'), timeout=2) as res:
            assert res.status == 200
        # Simulate an operator closing the program window.
        return None

    monkeypatch.setitem(sys.modules, 'webview', types.SimpleNamespace(create_window=create_window, start=start))
    launcher.run_desktop(staging=True)
    assert created['gui'] == 'edgechromium'
    assert created['url'].endswith(':8766/admin')
    assert created['opts']['resizable'] is True
    assert created['opts']['confirm_close'] is True
    # We have stopped the HTTP server instead of leaving a background process.
    assert not launcher.port_is_busy('127.0.0.1', 8766)


def test_browser_panel_has_quit_button_only_for_native_window():
    html = (launcher.app_directory()/'modules/hj_players/frontend/admin.html').read_text(encoding='utf-8')
    assert 'id="quitDesktop"' in html
    assert 'pywebviewready' in html
    assert 'window.pywebview.api.quit()' in html
