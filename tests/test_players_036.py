"""Regression tests for HJ PLAYERS editor / overlay publication, v0.3.6."""
from fastapi.testclient import TestClient
from app.main import create_app


def test_assign_first_box_autoplaces_each_camera_without_overwriting_manual(tmp_path):
    with TestClient(create_app(tmp_path/'live.sqlite3')) as c:
        initial=c.post('/api/players', json={'nickname':'BUNNY','seat':None}).json()
        pid=initial['players'][0]['id']
        assert initial['profiles']['top']['placements'][pid]['x']==.5
        # Manually placed in SIDE profile: this must be preserved.
        manual={**initial['profiles']['side']['placements'][pid], 'x':.22,'y':.76,'rotation':90}
        updated=c.put('/api/profiles/side/draft',json={'placements':{pid:manual}})
        assert updated.status_code==200,updated.text
        c.post('/api/profiles/side/publish')
        result=c.patch(f'/api/players/{pid}',json={'seat':6})
        assert result.status_code==200,result.text
        body=result.json()
        assert (body['profiles']['top']['placements'][pid]['x'],body['profiles']['top']['placements'][pid]['y'])==(.89,.70)
        assert (body['profiles']['front']['placements'][pid]['x'],body['profiles']['front']['placements'][pid]['y'])==(.81,.83)
        assert body['profiles']['side']['placements'][pid]==manual
        # Switching an already assigned box must not override a careful layout.
        follow=c.patch(f'/api/players/{pid}',json={'seat':9}).json()
        assert (follow['profiles']['top']['placements'][pid]['x'],follow['profiles']['top']['placements'][pid]['y'])==(.89,.70)
        assert follow['profiles']['side']['placements'][pid]==manual


def test_legacy_centered_player_can_be_rearranged_as_draft_without_touching_on_air(tmp_path):
    db=tmp_path/'live.sqlite3'
    with TestClient(create_app(db)) as c:
        initial=c.post('/api/players',json={'nickname':'ROX','seat':2}).json()
        pid=initial['players'][0]['id']
        untouched=initial['profiles']['top']['placements'][pid]
        legacy={**untouched,'x':.5,'y':.5,'rotation':90}
        c.put('/api/profiles/top/draft',json={'placements':{pid:legacy}})
        c.post('/api/profiles/top/publish')
        moved=c.post('/api/profiles/top/auto-place')
        assert moved.status_code==200,moved.text
        snapshot=moved.json()
        assert snapshot['profiles']['top']['placements'][pid]==legacy
        pending=snapshot['drafts']['top'][pid]
        assert (pending['x'],pending['y'])==(.39,.09)
        assert pending['rotation']==90
        assert snapshot['profiles']['front']['placements'][pid]['rotation']==0
        assert snapshot['profiles']['side']['placements'][pid]['rotation']==0
        published=c.post('/api/profiles/top/publish')
        assert published.status_code==200
        assert published.json()['profiles']['top']['placements'][pid]==pending
    with TestClient(create_app(db)) as c:
        assert c.get('/api/state').json()['profiles']['top']['placements'][pid]==pending


def test_first_seat_assignment_preserves_draft_custom_position_and_autoplaces_default(tmp_path):
    with TestClient(create_app(tmp_path/'live.sqlite3')) as c:
        state=c.post('/api/players',json={'nickname':'JACK','seat':None}).json()
        pid=state['players'][0]['id']
        top={**state['profiles']['top']['placements'][pid], 'x':.34,'y':.42}
        side=state['profiles']['side']['placements'][pid]
        c.put('/api/profiles/top/draft',json={'placements':{pid:top}})
        c.put('/api/profiles/side/draft',json={'placements':{pid:side}})
        next_state=c.patch(f'/api/players/{pid}',json={'seat':5}).json()
        assert next_state['drafts']['top'][pid]==top
        assert (next_state['drafts']['side'][pid]['x'],next_state['drafts']['side'][pid]['y'])==(.86,.50)
        assert (next_state['profiles']['top']['placements'][pid]['x'],next_state['profiles']['top']['placements'][pid]['y'])==(.89,.31)


def test_rotation_published_and_seen_by_overlay_state(tmp_path):
    with TestClient(create_app(tmp_path/'live.sqlite3')) as c:
        player=c.post('/api/players',json={'nickname':'LEFT SIDE','seat':1}).json()
        pid=player['players'][0]['id']
        rotation={**player['profiles']['top']['placements'][pid], 'rotation':-90}
        with c.websocket_connect('/ws?client=overlay') as ws:
            assert ws.receive_json()['type']=='state'
            c.put('/api/profiles/top/draft',json={'placements':{pid:rotation}})
            assert ws.receive_json()['type']=='state'
            result=c.post('/api/profiles/top/publish')
            assert result.status_code==200
            update=ws.receive_json()
            assert update['type']=='state'
            assert update['state']['profiles']['top']['placements'][pid]['rotation']==-90
