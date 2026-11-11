"""HI, JACK LIVE CORE. External modules provide user-facing functionality."""
from __future__ import annotations
import asyncio
import copy
import json
import logging
import shutil
import os
import sys
import time
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request,WebSocket,WebSocketDisconnect,Depends
from fastapi.responses import FileResponse,RedirectResponse,JSONResponse
from .state import StateStore,validate_import
from core.runtime import HostRuntime,SocketHub,HOST_API_VERSION
from core.module_loader import ModuleLoader
from core.update_manager import UpdateManager,PackageError,MAX_ZIP_BYTES

RESOURCE_ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
DATA_DIR=Path(os.environ.get('HJ_DATA_DIR',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'HiJackLive'/'production'))).resolve()
MODULES_DIR=Path(os.environ.get('HJ_MODULES_DIR',
    str((Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else RESOURCE_ROOT)/'modules'))).resolve()
TOKEN=os.environ.get('HJ_ADMIN_TOKEN','')
log=logging.getLogger('hijack-live')


def create_app(db_path:Path|None=None,modules_dir:Path|None=None,_recovered:bool=False)->FastAPI:
    db_path=Path(db_path or (DATA_DIR/'hi-jack.sqlite3')).resolve()
    data_dir=db_path.parent
    store=StateStore(db_path)
    hub=SocketHub()
    host=HostRuntime(store,hub,data_dir,TOKEN)
    module_dir=Path(modules_dir or MODULES_DIR)
    loader=ModuleLoader(module_dir,data_dir)
    updates=UpdateManager(module_dir,data_dir)
    app=FastAPI(title='HI, JACK LIVE CORE',version='0.3.5',docs_url=None,redoc_url=None)
    app.state.store=store
    app.state.runtime=host
    app.state.module_loader=loader
    app.state.update_manager=updates
    update_lock=asyncio.Lock()
    app.state.ui_heartbeat_time = 0.0
    app.state.ui_heartbeat_page = ""

    @app.middleware('http')
    async def trace_mutations(request:Request, call_next):
        method, path = request.method, request.url.path
        if method not in ('POST','PATCH','PUT','DELETE') or path.startswith('/api/desktop/'):
            return await call_next(request)
        started=time.monotonic()
        log.info('API_BEGIN %s %s', method, path)
        try:
            response=await call_next(request)
            log.info('API_END %s %s status=%d elapsed_ms=%d', method, path,
                     response.status_code, int((time.monotonic()-started)*1000))
            return response
        except Exception:
            log.exception('API_FAIL %s %s elapsed_ms=%d',method,path,int((time.monotonic()-started)*1000))
            raise

    @app.post('/api/desktop/heartbeat')
    async def ui_heartbeat(request:Request):
        # Diagnostics only. Never store nicknames, credentials or API keys.
        if int(request.headers.get('content-length') or 0) > 512:
            raise HTTPException(413,'Too large')
        raw=await request.json()
        page=str(raw.get('page',''))[:40] if isinstance(raw,dict) else ''
        app.state.ui_heartbeat_time=time.monotonic()
        if page != app.state.ui_heartbeat_page:
            log.info('UI_ACTIVE page=%s',page)
            app.state.ui_heartbeat_page=page
        return {'ok':True}

    @app.post('/api/desktop/client-error')
    async def ui_error(request:Request):
        if int(request.headers.get('content-length') or 0) > 1024:
            raise HTTPException(413,'Too large')
        raw=await request.json()
        if not isinstance(raw,dict):raise HTTPException(400,'Invalid diagnostics')
        # Do not log entire stack traces or arbitrary page URLs, which can include private data.
        kind=str(raw.get('kind','unknown'))[:50]
        message=str(raw.get('message',''))[:260].replace('\n',' ')
        log.warning('UI_JS_ERROR kind=%s message=%s',kind,message)
        return {'ok':True}

    async def admin_only(request:Request):
        return await host.admin_only(request)

    @app.get('/')
    def root():return RedirectResponse('/admin')

    @app.get('/favicon.ico')
    def app_icon():return FileResponse(RESOURCE_ROOT/'branding/HiJackLive.ico',media_type='image/x-icon')

    @app.get('/static/common.js')
    def common_js():return FileResponse(RESOURCE_ROOT/'core/ui/common.js',media_type='text/javascript')

    @app.get('/modules')
    def modules_page():return FileResponse(RESOURCE_ROOT/'core/ui/modules.html')

    @app.get('/static/modules.js')
    def modules_js():return FileResponse(RESOURCE_ROOT/'core/ui/modules.js',media_type='text/javascript')

    @app.get('/health')
    def health():return {'ok':True,'service':'HI JACK LIVE CORE','host_api':HOST_API_VERSION,
             'revision':store.state['revision'],'modules_loaded':sum(r.status=='loaded' for r in loader.records.values())}

    @app.get('/api/state')
    def state():return copy.deepcopy(store.state)

    @app.websocket('/ws')
    async def realtime(ws:WebSocket):
        role=ws.query_params.get('client','admin')
        await hub.connect(ws,store.state,role)
        try:
            while True:await ws.receive_text()
        except WebSocketDisconnect:pass
        finally:hub.connections.pop(ws,None)

    @app.post('/api/undo',dependencies=[Depends(admin_only)])
    async def undo():
        async with host.lock:
            try:restored=store.undo()
            except ValueError as exc:raise HTTPException(400,str(exc)) from exc
            await hub.broadcast({'type':'state','state':restored})
        await host.events.publish('state.changed',{'revision':restored['revision']})
        return restored

    @app.get('/api/config/export',dependencies=[Depends(admin_only)])
    def export_config():return JSONResponse(store.state,headers={'Content-Disposition':'attachment; filename=hi-jack-live-config.json'})

    @app.post('/api/config/import',dependencies=[Depends(admin_only)])
    async def import_config(request:Request):
        raw=await request.body()
        if len(raw)>500_000:raise HTTPException(413,'Файл слишком большой')
        try:restored=validate_import(json.loads(raw))
        except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
        themes=host.services.get('players.api')
        if themes is not None:
            for tid in [restored['settings']['theme']] + [p.get('theme') for p in restored['players']+[restored['dealer']]]:
                if not themes.theme_exists(tid):raise HTTPException(400,'Тема не установлена')
        store.backup()
        return await host.change(lambda state:(state.clear(),state.update(restored)))

    @app.post('/api/config/backup',dependencies=[Depends(admin_only)])
    def backup():return {'ok':True,'filename':store.backup().name}

    @app.get('/api/modules',dependencies=[Depends(admin_only)])
    def modules_status():
        return {'host_api':HOST_API_VERSION,'modules':loader.public_status(),
                'overlay_connections':hub.overlays_online,'ui':host.registered_ui}

    async def read_package(request:Request):
        if request.headers.get('content-type','').split(';')[0]!='application/zip':
            raise HTTPException(415,'Отправьте ZIP с Content-Type: application/zip')
        content=await request.body()
        if len(content)>MAX_ZIP_BYTES:raise HTTPException(413,'ZIP превышает лимит')
        return content

    @app.post('/api/modules/validate',dependencies=[Depends(admin_only)])
    async def validate_module(request:Request):
        try:return updates.validate(await read_package(request))
        except Exception as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.post('/api/modules/install',dependencies=[Depends(admin_only)])
    async def install_module(request:Request):
        async with update_lock:
            if hub.overlays_online:
                raise HTTPException(409,'OBS-оверлей подключён. Установку проводите после завершения трансляции')
            try:
                package=await read_package(request)
                # Snapshot user state; module code lives in a different directory.
                store.backup()
                return updates.install(package,loader.capabilities)
            except Exception as exc:
                raise HTTPException(400,str(exc)) from exc

    @app.post('/api/modules/{module_id}/rollback',dependencies=[Depends(admin_only)])
    async def rollback(module_id:str):
        async with update_lock:
            if hub.overlays_online:raise HTTPException(409,'Остановите эфир перед откатом')
            try:return updates.rollback(module_id)
            except Exception as exc:raise HTTPException(400,str(exc)) from exc

    @app.post('/api/modules/{module_id}/disable',dependencies=[Depends(admin_only)])
    async def disable_module(module_id:str,disabled:bool=True):
        if hub.overlays_online:raise HTTPException(409,'Остановите эфир для изменения модулей')
        if module_id not in loader.records:raise HTTPException(404,'Модуль не найден')
        loader.set_disabled(module_id,disabled)
        return {'ok':True,'restart_required':True,'disabled':disabled}

    loader.register(app,host)
    # If an installed module fails its boot-time self-check / registration after an
    # update, restore the previous module folder and rebuild the app once.
    if not _recovered:
        recovered=False
        for ident,record in loader.records.items():
            if record.status=='error' and (updates.backup_root/ident.replace('.','_')).exists():
                try:
                    updates.rollback(ident)
                    log.error('Auto-restored last working version of %s after startup failure: %s',ident,record.error)
                    recovered=True
                except Exception:log.exception('Cannot auto-rollback %s',ident)
        if recovered:return create_app(db_path,module_dir,_recovered=True)
    return app

app=create_app()
