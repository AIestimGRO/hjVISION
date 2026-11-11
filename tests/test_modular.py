"""Real compatibility and offline update tests for CORE API 1.x."""
from __future__ import annotations
import copy
import io
import json
import shutil
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from core.module_loader import ModuleLoader,check_manifest,probe_module
from core.runtime import EventBus
from core.update_manager import UpdateManager,PackageError,write_checksums
from core.storage import NamespaceStorage
from app.main import create_app

ROOT=Path(__file__).resolve().parents[1]


def sandbox(tmp_path):
    mods=tmp_path/'modules'
    shutil.copytree(ROOT/'modules',mods,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc'))
    db=tmp_path/'user_data'/'live.sqlite3'
    return mods,db


def make_package(folder, version=None, mutate=None):
    # Bundle a copy, so tests never alter the installed module or other modules.
    with __import__('tempfile').TemporaryDirectory() as td:
        tmp=Path(td)/folder.name
        shutil.copytree(folder,tmp,ignore=shutil.ignore_patterns('checksums.json','__pycache__','*.pyc'))
        if version:
            data=json.loads((tmp/'module.json').read_text())
            data['version']=version
            (tmp/'module.json').write_text(json.dumps(data))
        if mutate:mutate(tmp)
        write_checksums(tmp)
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            for file in tmp.rglob('*'):
                if file.is_file():z.write(file,arcname=f'{tmp.name}/{file.relative_to(tmp).as_posix()}')
        return buf.getvalue()


def test_external_loader_two_modules_and_six_placeholders(tmp_path):
    mods,db=sandbox(tmp_path)
    with TestClient(create_app(db,modules_dir=mods)) as c:
        data=c.get('/api/modules').json()
        status={m['id']:m['status'] for m in data['modules']}
        assert status['hj.players']=='loaded'
        assert status['hj.effects']=='loaded'
        assert sum(x=='disabled' for x in status.values())==6
        assert c.get('/admin').status_code==200
        assert c.get('/overlay/players').status_code==200
        assert c.get('/overlay/effects').status_code==200
        assert c.get('/modules').status_code==200
        assert c.get('/static/modules.js').status_code==200


def test_player_can_move_to_a_new_module_bundle_without_data_loss(tmp_path):
    mods,db=sandbox(tmp_path)
    with TestClient(create_app(db,modules_dir=mods)) as c:
        r=c.post('/api/players',json={'nickname':'BLUFF DADDY','seat':7}).json()
        player_id=r['players'][0]['id']
        c.put('/api/profiles/top/draft',json={'placements':{player_id:{**r['profiles']['top']['placements'][player_id],'width':.22}}})
        c.post('/api/profiles/top/publish')
        c.post('/api/settings',json={'theme':'silver-blue'})
        old=c.get('/api/state').json()
        payload=make_package(mods/'hj_players',version='0.3.9',mutate=lambda folder:(folder/'CHANGELOG.md').write_text('Extra update'))
        assert c.post('/api/modules/validate',content=payload,headers={'Content-Type':'application/zip'}).json()['version']=='0.3.9'
        result=c.post('/api/modules/install',content=payload,headers={'Content-Type':'application/zip'})
        assert result.status_code==200,result.text
        assert result.json()['restart_required'] is True
    with TestClient(create_app(db,modules_dir=mods)) as c:
        state=c.get('/api/state').json()
        assert state['players']==old['players']
        assert state['profiles']==old['profiles']
        assert state['settings']==old['settings']
        assert {m['id']:m['version'] for m in c.get('/api/modules').json()['modules']}['hj.players']=='0.3.9'
        assert check_manifest(mods/'hj_players')['version']=='0.3.9'
        rollback=c.post('/api/modules/hj.players/rollback')
        assert rollback.status_code==200,rollback.text
    assert check_manifest(mods/'hj_players')['version']=='0.3.10'
    with TestClient(create_app(db,modules_dir=mods)) as c:
        assert c.get('/api/state').json()['players']==old['players']


def test_reject_wrong_api_and_modified_files_without_mutating_module(tmp_path):
    mods,db=sandbox(tmp_path)
    updater=UpdateManager(mods,db.parent)
    before=(mods/'hj_players/module.json').read_bytes()
    def break_api(folder):
        p=folder/'module.json';d=json.loads(p.read_text());d['host_api']='2.x';p.write_text(json.dumps(d))
    bad=make_package(mods/'hj_players',version='0.4.0',mutate=break_api)
    with pytest.raises(ValueError,match='Incompatible'):updater.validate(bad)
    good=make_package(mods/'hj_players',version='0.3.9')
    buf=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(good)) as src, zipfile.ZipFile(buf,'w') as target:
        for entry in src.infolist():
            raw=src.read(entry.filename)
            if entry.filename.endswith('CHANGELOG.md'):raw=b'TAMPERED'
            target.writestr(entry.filename,raw)
    with pytest.raises(PackageError,match='checksum'):updater.validate(buf.getvalue())
    assert (mods/'hj_players/module.json').read_bytes()==before


def test_zip_traversal_refused(tmp_path):
    updater=UpdateManager(tmp_path/'modules',tmp_path/'data')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:z.writestr('hj_players/../../dangerous.txt','HACK')
    with pytest.raises(PackageError,match='Unsafe'):updater.validate(buf.getvalue())
    assert not (tmp_path/'dangerous.txt').exists()


def test_updating_forbidden_during_overlay_connection(tmp_path):
    mods,db=sandbox(tmp_path)
    payload=make_package(mods/'hj_players',version='0.3.9')
    with TestClient(create_app(db,modules_dir=mods)) as c:
        with c.websocket_connect('/ws?client=overlay') as ws:
            assert ws.receive_json()['type']=='state'
            assert c.get('/api/modules').json()['overlay_connections']==1
            r=c.post('/api/modules/install',content=payload,headers={'Content-Type':'application/zip'})
            assert r.status_code==409
        assert check_manifest(mods/'hj_players')['version']=='0.3.10'


def test_independent_disable_preserves_players(tmp_path):
    mods,db=sandbox(tmp_path)
    with TestClient(create_app(db,modules_dir=mods)) as c:
        c.post('/api/players',json={'nickname':'PLAYER1','seat':2})
        assert c.post('/api/modules/hj.effects/disable?disabled=true').status_code==200
    with TestClient(create_app(db,modules_dir=mods)) as c:
        status={m['id']:m['status'] for m in c.get('/api/modules').json()['modules']}
        assert status['hj.players']=='loaded' and status['hj.effects']=='disabled'
        assert c.get('/api/state').json()['players'][0]['nickname']=='PLAYER1'
        assert c.get('/overlay/players').status_code==200
        assert c.get('/overlay/effects').status_code==404


def test_failed_atomic_swap_restores_old_module(tmp_path,monkeypatch):
    mods,db=sandbox(tmp_path)
    updater=UpdateManager(mods,db.parent)
    payload=make_package(mods/'hj_players',version='0.3.9')
    import core.update_manager as mod
    real_replace=mod.os.replace
    def fail_replace(src,dst):
        if str(src).endswith('/hj_players') and '/updates/hj-stage-' in str(src) and Path(dst)==mods/'hj_players':
            raise OSError('Simulated disk failure')
        return real_replace(src,dst)
    monkeypatch.setattr(mod.os,'replace',fail_replace)
    with pytest.raises(OSError,match='Simulated'):updater.install(payload,{'core.events','core.state','core.storage'})
    assert check_manifest(mods/'hj_players')['version']=='0.3.10'


def test_event_bus_contract_and_namespaced_storage(tmp_path):
    events=[]
    bus=EventBus()
    bus.subscribe('player.added',events.append)
    import asyncio
    asyncio.run(bus.publish('player.added',{'player_id':'abc'},source='hj.players'))
    assert events[0]['type']=='player.added'
    assert events[0]['schema_version']=='1.0' and events[0]['event_id'] and events[0]['timestamp']
    players=NamespaceStorage(tmp_path,'hj.players')
    effects=NamespaceStorage(tmp_path,'hj.effects')
    players.set('foo',{'nickname':'JACK'})
    assert players.get('foo')['nickname']=='JACK'
    assert effects.get('foo') is None
    assert not str(players.path).startswith(str(ROOT/'modules'))


def test_module_data_migration_is_versioned_and_backed_up(tmp_path):
    mods,db=sandbox(tmp_path)
    folder=mods/'hj_players'
    manifest=json.loads((folder/'module.json').read_text())
    manifest['data_schema']=1
    (folder/'module.json').write_text(json.dumps(manifest))
    (folder/'migrations/0001_settings.py').write_text("def upgrade(storage):\n    storage.set('banner', 'BRONZE')\n")
    with TestClient(create_app(db,modules_dir=mods)) as c:
        assert {m['id']:m['status'] for m in c.get('/api/modules').json()['modules']}['hj.players']=='loaded'
    namespace=NamespaceStorage(db.parent/'module_data','hj.players')
    assert namespace.get('banner')=='BRONZE'
    assert namespace.get('__schema_version__')==1
    assert list((db.parent/'module_data/backups').glob('hj.players-before-v1-*.sqlite3'))


def test_startup_failing_updated_module_automatically_rolls_back(tmp_path):
    mods,db=sandbox(tmp_path)
    with TestClient(create_app(db,modules_dir=mods)) as c:
        c.post('/api/players',json={'nickname':'STILL HERE','seat':3})
        payload=make_package(mods/'hj_players',version='0.3.9')
        r=c.post('/api/modules/install',content=payload,headers={'Content-Type':'application/zip'})
        assert r.status_code==200
    assert check_manifest(mods/'hj_players')['version']=='0.3.9'
    path=mods/'hj_players/backend/plugin.py'
    code=path.read_text()
    path.write_text(code.replace("return clean_nickname('Тест')=='Тест' and 'compact' in ALLOWED_STYLES",'return False'))
    # Startup validates the updated module, sees the failed self-test,
    # restores last known module code, and constructs a fresh route table.
    with TestClient(create_app(db,modules_dir=mods)) as c:
        status={m['id']:m['status'] for m in c.get('/api/modules').json()['modules']}
        assert status['hj.players']=='loaded'
        assert c.get('/api/state').json()['players'][0]['nickname']=='STILL HERE'
    assert check_manifest(mods/'hj_players')['version']=='0.3.10'
