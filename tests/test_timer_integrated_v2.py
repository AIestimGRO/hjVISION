"""HJ TIMER v0.2 integrated UI / compatibility regression checks."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app

ROOT=Path(__file__).resolve().parents[1]


def test_single_window_timer_control_and_crisp_overlay(tmp_path):
    with TestClient(create_app(tmp_path/'user_data/live.sqlite3')) as c:
        panel=c.get('/admin')
        assert panel.status_code==200
        assert 'id="hjTimerWidget"' in panel.text
        assert 'id="hjTimerPanel"' in panel.text
        assert 'id="hjtPublish"' in panel.text
        assert '/module-assets/hj.timer_overlay/integrated.js' in panel.text
        assert 'aspect-ratio:16 / 9' in c.get('/static/graphics.css').text
        assert c.get('/module-assets/hj.timer_overlay/integrated.js').status_code==200
        visual=c.get('/module-assets/hj.timer_overlay/widget-v2.css')
        assert visual.status_code==200
        assert 'font-variant-numeric:tabular-nums' in visual.text
        assert 'gradient' in visual.text
        # Keep HJ PLAYERS controls intact — no global timer stylesheet may override them.
        assert '/module-assets/hj.timer_overlay/timer.css' not in panel.text


def test_box_numbers_hidden_from_audience_labels():
    admin=(ROOT/'modules/hj_players/frontend/admin.js').read_text('utf8')
    audience=(ROOT/'modules/hj_players/frontend/players.js').read_text('utf8')
    assert "if(!p.is_dealer)el.querySelector('.hj-caption')?.remove()" in admin
    assert "if(!player.is_dealer)badge.querySelector('.hj-caption')?.remove()" in audience
    # Internal seat assignments are still offered to operators.
    assert 'seatOptions' in admin


def test_timer_changes_publish_separately_from_players(tmp_path):
    with TestClient(create_app(tmp_path/'user_data/live.sqlite3')) as c:
        player=c.post('/api/players',json={'nickname':'JACK','seat':7}).json()
        original=player['profiles']['top']['placements'].copy()
        published=c.get('/api/hj-timer/layout?profile=top').json()['layout']
        amended={**published,'x':.7,'variant':'premium','width':.42}
        r=c.put('/api/hj-timer/draft/top',json=amended)
        assert r.status_code==200
        assert c.get('/api/hj-timer/layout?profile=top').json()['layout']==published
        result=c.post('/api/hj-timer/publish/top')
        assert result.status_code==200
        assert c.get('/api/hj-timer/layout?profile=top').json()['layout']==amended
        assert c.get('/api/state').json()['profiles']['top']['placements']==original
