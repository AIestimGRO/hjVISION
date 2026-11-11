import json
from fastapi.testclient import TestClient
import pytest
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(tmp_path / 'test.sqlite3')) as c:
        yield c


def add(c, nickname, seat):
    r=c.post('/api/players',json={'nickname':nickname,'seat':seat})
    assert r.status_code==200, r.text
    return r.json()['players'][-1]['id']


def test_root_and_overlay_assets(client):
    assert client.get('/').status_code in (200,307)
    assert client.get('/admin').status_code==200
    assert 'HI, JACK' in client.get('/admin').text
    assert client.get('/overlay/players?layout=top').status_code==200
    assert client.get('/overlay/effects').status_code==200
    assert client.get('/static/admin.js').status_code==200
    assert client.get('/health').json()['ok'] is True


def test_maximum_ten_seats_and_dealer(client):
    for i in range(1,11):add(client,f'Player {i}',i)
    r=client.post('/api/players',json={'nickname':'Extra','seat':None})
    assert r.status_code==400
    r=client.patch('/api/players/dealer',json={'visible':True,'nickname':'Дилер Максим'})
    assert r.status_code==200
    assert len(r.json()['players'])==10
    assert r.json()['dealer']['visible']
    assert r.json()['dealer']['nickname']=='Дилер Максим'
    assert len(r.json()['profiles']['top']['placements'])==11


def test_seat_conflict_and_seat_does_not_move_badge(client):
    first=add(client,'First',1)
    add(client,'Second',4)
    original=client.get('/api/state').json()['profiles']['top']['placements'][first]
    assert client.patch(f'/api/players/{first}',json={'seat':4}).status_code==400
    after=client.patch(f'/api/players/{first}',json={'seat':8})
    assert after.status_code==200
    assert after.json()['profiles']['top']['placements'][first]==original


def test_draft_not_live_and_profile_independence(client):
    pid=add(client,'JACK',3)
    original=client.get('/api/state').json()
    placement=original['profiles']['top']['placements'][pid]
    moved={**placement,'x':.77,'y':.44,'rotation':12}
    response=client.put('/api/profiles/top/draft',json={'placements':{pid:moved}})
    assert response.status_code==200, response.text
    assert response.json()['profiles']['top']['placements'][pid]==placement
    assert response.json()['drafts']['top'][pid]==moved
    published=client.post('/api/profiles/top/publish').json()
    assert published['profiles']['top']['placements'][pid]==moved
    assert published['profiles']['side']['placements'][pid] != moved
    assert 'top' not in published['drafts']


def test_replace_preserves_placement_and_delete_one(client):
    a=add(client,'A',7)
    b=add(client,'B',2)
    old=client.get('/api/state').json()['profiles']['top']['placements'][a]
    result=client.post(f'/api/players/{a}/replace',json={'nickname':'C','seat':None})
    assert result.status_code==200
    new=[p for p in result.json()['players'] if p['nickname']=='C'][0]
    assert new['id']!=a and new['seat']==7
    assert result.json()['profiles']['top']['placements'][new['id']]==old
    assert a not in result.json()['profiles']['top']['placements']
    response=client.delete(f"/api/players/{b}")
    assert response.status_code==200
    assert [p['nickname'] for p in response.json()['players']]==['C']


def test_undo_and_durable_reload(tmp_path):
    db=tmp_path/'app.sqlite3'
    c=TestClient(create_app(db))
    add(c,'Remember Me',6)
    c.post('/api/players/clear')
    assert not c.get('/api/state').json()['players']
    assert len(c.post('/api/undo').json()['players'])==1
    c.close()
    d=TestClient(create_app(db))
    assert d.get('/api/state').json()['players'][0]['nickname']=='Remember Me'
    d.close()


def test_effects_websocket_and_stop(client):
    with client.websocket_connect('/ws') as ws:
        snapshot=ws.receive_json()
        assert snapshot['type']=='state'
        r=client.post('/api/effects',json={'name':'ALL-IN','duration':1000})
        assert r.status_code==200
        effect=ws.receive_json()
        assert effect['type']=='effect' and effect['name']=='ALL-IN'
        client.post('/api/effects/stop')
        assert ws.receive_json()['type']=='effect-stop'


def test_export_import_validation_and_backup(client):
    pid=add(client,'Тест',2)
    exported=client.get('/api/config/export').json()
    assert exported['players'][0]['id']==pid
    assert client.post('/api/config/import',content=json.dumps({'players':[]})).status_code==400
    assert len(client.get('/api/state').json()['players'])==1
    client.post('/api/players/clear')
    imported=client.post('/api/config/import',content=json.dumps(exported))
    assert imported.status_code==200, imported.text
    assert len(imported.json()['players'])==1
    assert client.post('/api/config/backup').json()['ok']


def test_invalid_style_name_and_bad_placement(client):
    r=client.post('/api/players',json={'nickname':'X','seat':1,'style':'hack'})
    assert r.status_code==400
    pid=add(client,'X',1)
    r=client.put('/api/profiles/top/draft',json={'placements':{pid:{'x':5,'y':0}}})
    assert r.status_code==400
    assert client.get('/api/state').json()['drafts']=={}


def test_names_not_html_injection(client):
    add(client,'<img src=x>',1)
    assert client.get('/api/state').json()['players'][0]['nickname']=='<img src=x>'
    # UI renders escaped, never injects markup from nicknames.
    assert 'HJ.esc' in client.get('/static/admin.js').text

# Addendum №1: themes, scalable graphics and historical-layout migration.
def test_theme_packs_and_local_assets(client):
    data=client.get('/api/themes').json()
    assert {t['id'] for t in data['themes']} >= {
        'bronze-premium','silver-blue','red-gold','emerald','purple-chrome'
    }
    assert data['default']=='bronze-premium'
    for t in data['themes']:
        response=client.get(t['frame_url'])
        assert response.status_code==200
        assert '<svg' in response.text
        assert 'BLUFF DADDY' not in response.text
    overlay=client.get('/overlay/players').text
    assert '/static/graphics.css' in overlay


def test_global_theme_and_individual_override(client):
    pid=add(client,'BLUFF DADDY',3)
    previous=client.get('/api/state').json()
    pl=previous['profiles']['top']['placements'][pid]
    result=client.post('/api/settings',json={'theme':'silver-blue','default_style':'compact'})
    assert result.status_code==200
    assert result.json()['profiles']['top']['placements'][pid]==pl
    assert result.json()['settings']['theme']=='silver-blue'
    assert result.json()['players'][0]['nickname']=='BLUFF DADDY'
    changed=client.patch(f'/api/players/{pid}',json={'theme':'red-gold','nickname':'Семён ☺'})
    assert changed.status_code==200
    assert changed.json()['players'][0]['theme']=='red-gold'
    assert changed.json()['profiles']['top']['placements'][pid]==pl
    assert client.post('/api/settings',json={'theme':'unknown-theme'}).status_code==400
    assert client.patch(f'/api/players/{pid}',json={'theme':'uninstalled'}).status_code==400
    other=add(client,'New Player',4)
    players=client.get('/api/state').json()['players']
    new=[p for p in players if p['id']==other][0]
    assert new['theme'] is None and new['style'] is None
    assert result.json()['settings']['default_style']=='compact'


def test_independent_dimensions_and_published_draft(client):
    first=add(client,'FIRST',2)
    second=add(client,'SECOND',9)
    state=client.get('/api/state').json()
    baseline=state['profiles']['top']['placements']
    before=baseline[first]
    after={**before,'width':.27,'height':.095,'scale':.65,'font_size':19,
           'padding':3,'glow':.1,'rotation':37,'opacity':.7,'style':'compact'}
    r=client.put('/api/profiles/top/draft',json={'placements':{first:after}})
    assert r.status_code==200,r.text
    assert r.json()['profiles']['top']['placements'][first]==before
    assert r.json()['drafts']['top'][first]==after
    live=client.post('/api/profiles/top/publish').json()
    assert live['profiles']['top']['placements'][first]==after
    assert live['profiles']['top']['placements'][second]==baseline[second]
    assert live['profiles']['side']['placements'][first] != after
    assert client.put('/api/profiles/top/draft',json={'placements':{first:{**after,'scale':4}}}).status_code==400


def test_old_snapshot_upgrades_without_clearing_players(tmp_path):
    import sqlite3
    from app.state import initial_state
    old=initial_state(); old['settings']={'volume':.3,'effects_enabled':True}
    old['players'].append({'id':'old123','nickname':'СТАРЫЙ ИГРОК','seat':5,'style':'classic','status':'active','visible':True})
    old['profiles']['top']['placements']['old123']={'x':.2,'y':.4,'width':.16,'rotation':0,'opacity':1,'visible':True}
    db=tmp_path/'migration.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE snapshots (name TEXT PRIMARY KEY, content TEXT NOT NULL, updated_at TEXT NOT NULL)')
        conn.execute('INSERT INTO snapshots VALUES (?,?,?)',('current',json.dumps(old,ensure_ascii=False),'2026-11-11'))
    c=TestClient(create_app(db))
    restored=c.get('/api/state').json()
    assert restored['players'][0]['nickname']=='СТАРЫЙ ИГРОК'
    assert restored['settings']['theme']=='bronze-premium'
    assert restored['profiles']['top']['placements']['old123']['height']==.065
    assert restored['players'][0]['theme'] is None
    assert restored['schema_version']==2
    assert list((tmp_path/'backups').glob('before-v2-*.sqlite3'))
    c.close()


def test_external_theme_pack_without_recompiling(client, tmp_path):
    target=tmp_path.parent/'themes'/'custom-theme';target.mkdir(parents=True,exist_ok=True)
    (target/'theme.json').write_text(json.dumps({'id':'custom-theme','name':'CUSTOM THEME',
        'frame':'frame.svg','color':'#eeeeee','glow':'#eeeecc','accent':'#cccccc'}))
    (target/'frame.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    assert 'custom-theme' in {x['id'] for x in client.get('/api/themes').json()['themes']}
    assert client.post('/api/settings',json={'theme':'custom-theme'}).status_code==200
