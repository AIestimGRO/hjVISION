"""HJ Effects external plug-in. Uses players.api service; never imports hj_players."""
from __future__ import annotations
from pathlib import Path
from uuid import uuid4
from fastapi import Depends,HTTPException,Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
EFFECTS=['ALL-IN','PLAYER OUT','DOUBLE UP','WINNER','FINAL TABLE','BREAK','BOUNTY','JACKPOT']
class EffectIn(BaseModel):
    name:str
    player_id:str|None=None
    duration:int=Field(default=3100,ge=600,le=15000)
    sound:bool=True
class EffectsAPI:
    def __init__(self,ctx):self.ctx=ctx
    async def stop_all(self):await self.ctx.broadcast({'type':'effect-stop'})
class Plugin:
    def self_check(self):return 'ALL-IN' in EFFECTS
    def register(self,app,ctx,folder:Path):
        ui=folder/'frontend'
        app.mount('/module-assets/hj.effects',StaticFiles(directory=ui),name='effects-frontend')
        ctx.register_service('effects.api',EffectsAPI(ctx))
        ctx.register_ui('Эфирные эффекты','/overlay/effects')
        player_service=ctx.get_service('players.api')
        async def admin_only(request:Request):return await ctx.admin_only(request)
        @app.get('/overlay/effects')
        def effects():return FileResponse(ui/'effects.html')
        @app.get('/static/effects.js')
        def effects_js():return FileResponse(ui/'effects.js',media_type='text/javascript')
        @app.post("/api/effects", dependencies=[Depends(admin_only)])
        async def play_effect(body: EffectIn):
            if body.name not in EFFECTS: raise HTTPException(400,"Неизвестный эффект")
            player = None
            if body.player_id:
                try: player = player_service.get_player(body.player_id) or (_ for _ in ()).throw(ValueError('Игрок не найден'))
                except ValueError as exc: raise HTTPException(400,str(exc)) from exc
            event = {"type":"effect","event_id":str(uuid4()),"name":body.name,
                     "nickname":player["nickname"] if player else "", "duration":body.duration,
                     "sound":body.sound, "volume":ctx.state()['settings']['volume']}
            await ctx.broadcast(event)
            return {"ok":True,"event_id":event["event_id"]}

        @app.post("/api/effects/stop", dependencies=[Depends(admin_only)])
        async def stop_effects():
            await ctx.broadcast({"type":"effect-stop"})
            return {"ok":True}


def create_plugin():return Plugin()
