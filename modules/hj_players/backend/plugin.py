"""HJ Players external plug-in. Owns seating, camera profiles, admin UI and theme assets."""
from __future__ import annotations
import copy
import json
import os
import re
from pathlib import Path
from uuid import uuid4
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
# Player rules are inside THIS ZIP. Persisted state-v2 contract is kept stable.
from .rules import (ALLOWED_STATUSES, ALLOWED_STYLES, DEFAULT_THEME, THEME_ID_RE,
                       clean_nickname,clean_seat,clean_placement,ensure_placements,
                       reposition_on_first_seat,default_placement,badge_visual_settings,configured_default_placement)

class PlayerIn(BaseModel):
    nickname:str
    seat:int|None=None
    style:str|None=None
    theme:str|None=None

class PlayerPatch(BaseModel):
    nickname:str|None=None
    seat:int|None=None
    visible:bool|None=None
    style:str|None=None
    theme:str|None=None
    status:str|None=None

class ProfileIn(BaseModel):
    name:str

class PlacementsIn(BaseModel):
    placements:dict[str,dict]

class BadgePresetIn(BaseModel):
    placement:dict

class SettingsIn(BaseModel):
    volume:float|None=Field(default=None,ge=0,le=1)
    theme:str|None=None
    default_style:str|None=None

class PlayersAPI:
    # Public service contract players.api v1.0; consumers use ctx.get_service().
    def __init__(self,ctx):self.ctx=ctx
    def theme_exists(self,theme_id):
        return theme_id is None or (hasattr(self,'themes') and theme_id in {t['id'] for t in self.themes()})
    def get_active_players(self):
        state=self.ctx.state()
        return [p for p in state['players'] if p['visible'] and p['status']!='out']
    def get_player(self,player_id):
        state=self.ctx.state()
        if player_id=='dealer':return state['dealer']
        return next((p for p in state['players'] if p['id']==player_id),None)

class Plugin:
    def self_check(self):
        return clean_nickname('Тест')=='Тест' and 'compact' in ALLOWED_STYLES

    def register(self,app,ctx,folder:Path):
        ui=folder/'frontend'
        theme_dir=folder/'assets'/'themes'
        custom_theme_dir=Path(os.environ.get('HJ_THEME_DIR',str(ctx.user_data_dir.parent/'themes'))).resolve()
        custom_theme_dir.mkdir(parents=True,exist_ok=True)
        app.mount('/themes',StaticFiles(directory=theme_dir),name='themes')
        app.mount('/custom-themes',StaticFiles(directory=custom_theme_dir),name='custom-themes')
        app.mount('/module-assets/hj.players',StaticFiles(directory=ui),name='players-frontend')
        player_service=PlayersAPI(ctx)
        ctx.register_service('players.api',player_service)
        ctx.register_ui('Игроки и рассадка','/admin')

        def installed_themes():
            themes={}
            for path,prefix in ((theme_dir,'/themes'),(custom_theme_dir,'/custom-themes')):
                if not path.exists():continue
                for file in sorted(path.glob('*/theme.json')):
                    if not THEME_ID_RE.fullmatch(file.parent.name):continue
                    try:
                        spec=json.loads(file.read_text(encoding='utf-8'))
                        if spec.get('id')!=file.parent.name:continue
                        if spec.get('frame')!='frame.svg' or not (file.parent/'frame.svg').is_file():continue
                        if not all(isinstance(spec.get(k),str) for k in ('name','color','glow','accent')):continue
                        themes[spec['id']]={**{k:spec[k] for k in ('id','name','frame','color','glow','accent')},
                            'frame_url':f"{prefix}/{spec['id']}/frame.svg"}
                    except (OSError,ValueError):continue
            return list(themes.values())

        player_service.themes=installed_themes

        def require_theme(theme):
            if theme is not None and (not isinstance(theme,str) or theme not in {p['id'] for p in installed_themes()}):
                raise ValueError('Тема не установлена. Установите комплект ресурсов и повторите')
            return theme

        async def admin_only(request:Request):
            return await ctx.admin_only(request)

        def find_player(state,pid):
            if pid=='dealer':return state['dealer']
            for p in state['players']:
                if p['id']==pid:return p
            raise ValueError('Игрок не найден')

        async def change(mutator):
            before=ctx.state()
            result=await ctx.change(mutator)
            old={p['id']:p for p in before['players']}
            new={p['id']:p for p in result['players']}
            for pid in new.keys()-old.keys():
                await ctx.events.publish('player.added',{'player_id':pid,'nickname':new[pid]['nickname'],'seat':new[pid]['seat']})
            for pid in old.keys()-new.keys():
                await ctx.events.publish('player.removed',{'player_id':pid})
            for pid in new.keys()&old.keys():
                if old[pid]!=new[pid]:
                    await ctx.events.publish('player.updated',{'player_id':pid,'nickname':new[pid]['nickname'],'status':new[pid]['status']})
                    if old[pid]['seat']!=new[pid]['seat']:
                        await ctx.events.publish('seat.changed',{'player_id':pid,'old_seat':old[pid]['seat'],'seat':new[pid]['seat']})
            return result

        @app.get('/admin')
        def admin():return FileResponse(ui/'admin.html')

        @app.get('/overlay/players')
        def players():return FileResponse(ui/'players.html')

        @app.get('/static/admin.js')
        def admin_js():return FileResponse(ui/'admin.js',media_type='text/javascript')

        @app.get('/static/players.js')
        def players_js():return FileResponse(ui/'players.js',media_type='text/javascript')

        @app.get('/static/graphics.css')
        def graphics_css():return FileResponse(ui/'graphics.css',media_type='text/css')

        @app.get('/static/style.css')
        def style_css():return FileResponse(ui/'style.css',media_type='text/css')

        # Service resolver remains compatible as new themes are installed.
        @app.get('/api/themes')
        def themes():return {'themes':installed_themes(),'default':DEFAULT_THEME}

        @app.post("/api/players/default-badge", dependencies=[Depends(admin_only)])
        async def save_default_badge(body: BadgePresetIn):
            """Remember visual properties only. Do not move or restyle existing live badges."""
            try:
                preset = badge_visual_settings(body.placement)
            except (ValueError, TypeError) as exc:
                raise HTTPException(400, str(exc)) from exc
            def mutate(state):
                state.setdefault("settings", {})["badge_default"] = preset
            return await change(mutate)

        @app.post("/api/profiles/{profile_id}/apply-badge-default", dependencies=[Depends(admin_only)])
        async def apply_badge_default(profile_id: str):
            """Apply current default to player badges in a draft, preserving x/y/visibility."""
            def mutate(state):
                if profile_id not in state["profiles"]:
                    raise ValueError("Профиль не найден")
                preset = state.get("settings", {}).get("badge_default")
                if not isinstance(preset, dict):
                    raise ValueError("Сначала сохраните стандарт оформления плашки")
                visual = badge_visual_settings(preset)
                draft = copy.deepcopy(state["drafts"].get(profile_id, state["profiles"][profile_id]["placements"]))
                for player in state["players"]:
                    placement = draft.get(player["id"])
                    if placement is None:
                        placement = configured_default_placement(state, player.get("seat"), profile_id)
                    draft[player["id"]] = clean_placement({**placement, **visual})
                state["drafts"][profile_id] = draft
            return await change(mutate)

        @app.post("/api/players", dependencies=[Depends(admin_only)])
        async def add_player(body: PlayerIn):
            def mutate(state):
                if len(state["players"]) >= 10: raise ValueError("Максимум 10 игроков за столом")
                style = body.style
                if style is not None and style not in ALLOWED_STYLES: raise ValueError("Неизвестный стиль")
                theme = require_theme(body.theme)
                new = {"id":str(uuid4()),"nickname":clean_nickname(body.nickname),
                       "seat":clean_seat(body.seat,state["players"]),"visible":True,
                       "style":style,"theme":theme,"status":"active","is_dealer":False}
                state["players"].append(new)
                ensure_placements(state,new)
            return await change(mutate)

        @app.patch("/api/players/{pid}", dependencies=[Depends(admin_only)])
        async def update_player(pid: str, body: PlayerPatch):
            payload = body.model_dump(exclude_unset=True)
            def mutate(state):
                p = find_player(state,pid)
                old_seat = p.get("seat")
                for k,v in payload.items():
                    if k == "nickname": v = clean_nickname(v)
                    elif k == "seat":
                        if pid == "dealer": raise ValueError("Дилеру нельзя назначить бокс")
                        v = clean_seat(v,state["players"],pid)
                    elif k == "status" and v not in ALLOWED_STATUSES: raise ValueError("Неверный статус")
                    elif k == "style" and v is not None and v not in ALLOWED_STYLES: raise ValueError("Неверный стиль")
                    elif k == "theme": v = require_theme(v)
                    elif k == "visible" and not isinstance(v,bool): raise ValueError("Неверная видимость")
                    p[k] = v
                if "seat" in payload:
                    reposition_on_first_seat(state, p, old_seat)
            return await change(mutate)

        @app.post("/api/players/{pid}/replace", dependencies=[Depends(admin_only)])
        async def replace_player(pid: str, body: PlayerIn):
            def mutate(state):
                if pid == "dealer": raise ValueError("Нельзя заменить дилера")
                old = find_player(state,pid)
                style = body.style
                if style is not None and style not in ALLOWED_STYLES: raise ValueError("Неизвестный стиль")
                theme = require_theme(body.theme)
                seat = old["seat"] if body.seat is None else clean_seat(body.seat,state["players"],pid)
                new_id = str(uuid4())
                idx = state["players"].index(old)
                state["players"][idx] = {"id":new_id,"nickname":clean_nickname(body.nickname),
                  "seat":seat,"visible":True,"style":style,"theme":theme,"status":"active","is_dealer":False}
                for layout in [p["placements"] for p in state["profiles"].values()] + list(state["drafts"].values()):
                    if pid in layout: layout[new_id] = layout.pop(pid)
            return await change(mutate)

        @app.delete("/api/players/{pid}", dependencies=[Depends(admin_only)])
        async def remove_player(pid: str):
            def mutate(state):
                if pid == "dealer": raise ValueError("Нельзя удалить дилера")
                find_player(state,pid)
                state["players"] = [p for p in state["players"] if p["id"] != pid]
                for layout in [p["placements"] for p in state["profiles"].values()] + list(state["drafts"].values()):
                    layout.pop(pid,None)
            return await change(mutate)

        @app.post("/api/players/clear", dependencies=[Depends(admin_only)])
        async def clear_players():
            def mutate(state):
                ids = {p["id"] for p in state["players"]}
                state["players"] = []
                for layout in [p["placements"] for p in state["profiles"].values()] + list(state["drafts"].values()):
                    for pid in ids: layout.pop(pid,None)
            return await change(mutate)

        @app.post("/api/players/reset-statuses", dependencies=[Depends(admin_only)])
        async def reset_statuses():
            def mutate(state):
                for p in state["players"]: p["status"] = "active"
            return await change(mutate)

        @app.post("/api/profiles", dependencies=[Depends(admin_only)])
        async def create_profile(body: ProfileIn):
            def mutate(state):
                if len(state["profiles"]) >= 30: raise ValueError("Максимум 30 профилей")
                name = body.name.strip()
                if not 1<=len(name)<=40: raise ValueError("Укажите название профиля")
                key = re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-") or f"custom-{len(state['profiles'])+1}"
                if key in state["profiles"]: key = f"{key}-{str(uuid4())[:5]}"
                state["profiles"][key] = {"name": name, "placements": {}}
                for p in state["players"] + [state["dealer"]]: ensure_placements(state,p)
                state["active_profile"] = key
            return await change(mutate)

        @app.post("/api/profiles/{profile_id}/activate", dependencies=[Depends(admin_only)])
        async def activate_profile(profile_id: str):
            def mutate(state):
                if profile_id not in state["profiles"]: raise ValueError("Профиль не найден")
                state["active_profile"] = profile_id
            return await change(mutate)

        @app.put("/api/profiles/{profile_id}/draft", dependencies=[Depends(admin_only)])
        async def save_draft(profile_id: str, body: PlacementsIn):
            def mutate(state):
                if profile_id not in state["profiles"]: raise ValueError("Профиль не найден")
                ids = {p["id"] for p in state["players"]} | {"dealer"}
                if set(body.placements) - ids: raise ValueError("Раскладка содержит неизвестных игроков")
                draft = copy.deepcopy(state["drafts"].get(profile_id, state["profiles"][profile_id]["placements"]))
                for pid,placement in body.placements.items(): draft[pid] = clean_placement(placement)
                state["drafts"][profile_id] = draft
            return await change(mutate)

        @app.post("/api/profiles/{profile_id}/auto-place", dependencies=[Depends(admin_only)])
        async def auto_place(profile_id: str):
            """Explicitly reposition current-profile badges in a DRAFT only.

            This also repairs legacy players who already have seats but were
            left at the screen center. Never silently touches the live overlay.
            """
            def mutate(state):
                if profile_id not in state["profiles"]:
                    raise ValueError("Профиль не найден")
                draft = copy.deepcopy(state["drafts"].get(profile_id, state["profiles"][profile_id]["placements"]))
                for player in state["players"]:
                    if player.get("seat") is None:
                        continue
                    placement = draft.get(player["id"])
                    if placement is None:
                        placement = default_placement(player["seat"], profile_id)
                    target = default_placement(player["seat"], profile_id)
                    draft[player["id"]] = {**placement, "x": target["x"], "y": target["y"]}
                state["drafts"][profile_id] = draft
            return await change(mutate)

        @app.post("/api/profiles/{profile_id}/publish", dependencies=[Depends(admin_only)])
        async def publish_draft(profile_id: str):
            def mutate(state):
                if profile_id not in state["profiles"]: raise ValueError("Профиль не найден")
                if profile_id in state["drafts"]:
                    state["profiles"][profile_id]["placements"] = state["drafts"].pop(profile_id)
            return await change(mutate)

        @app.post("/api/profiles/{profile_id}/discard", dependencies=[Depends(admin_only)])
        async def discard_draft(profile_id: str):
            def mutate(state):
                if profile_id not in state["profiles"]: raise ValueError("Профиль не найден")
                state["drafts"].pop(profile_id,None)
            return await change(mutate)

        @app.post("/api/settings", dependencies=[Depends(admin_only)])
        async def settings(body: SettingsIn):
            updates = body.model_dump(exclude_unset=True)
            if "theme" in updates:
                if updates["theme"] is None: raise HTTPException(400,"Укажите общую тему")
                try: require_theme(updates["theme"])
                except ValueError as exc: raise HTTPException(400,str(exc)) from exc
            if "default_style" in updates and updates["default_style"] not in ALLOWED_STYLES:
                raise HTTPException(400,"Неверный шаблон по умолчанию")
            return await change(lambda state: state["settings"].update(updates))


def create_plugin():return Plugin()
