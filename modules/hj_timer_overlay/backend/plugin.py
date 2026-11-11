"""Read-only bridge to HI, JACK TIMER with independently editable OBS layout.

No dependencies on HJ Players internals; no changes to the remote tournament timer.
"""
from __future__ import annotations
import asyncio
import copy
import json
import logging
import math
import time
from pathlib import Path
from urllib import request as urlrequest

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

log = logging.getLogger('hijack.timer_overlay')
# Deliberately fixed endpoint: never accept an arbitrary URL from the browser (SSRF prevention).
TIMER_URL = 'https://timer.hijackpoker.ru/api/state'
PROFILE_IDS = ('top', 'side', 'extra')
SAMPLE_SEC = 1.5
TIMEOUT_SEC = 2.5
MAX_RESPONSE = 64 * 1024

DEFAULT_LAYOUT = {'x': .50, 'y': .09, 'width': .285, 'visible': True,
                  'variant': 'horizontal', 'opacity': .96, 'show_ante': True,
                  'show_level': True}


def initial_config():
    return {'published': {
                'top': dict(DEFAULT_LAYOUT),
                'side': {**DEFAULT_LAYOUT, 'x': .83, 'y': .12, 'width': .30},
                'extra': dict(DEFAULT_LAYOUT)},
            'drafts': {}, 'revision': 0}


def valid_profile(value):
    if value not in PROFILE_IDS:
        raise HTTPException(400, 'Неизвестный ракурс')
    return value


class LayoutInput(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=.18, le=.55)
    visible: bool = True
    variant: str = Field(pattern='^(horizontal|stacked|minimal|premium)$')
    opacity: float = Field(ge=.35, le=1)
    show_ante: bool = True
    show_level: bool = True


def normalize_layout(payload):
    data = LayoutInput.model_validate(payload).model_dump()
    if not all(math.isfinite(data[k]) for k in ('x', 'y', 'width', 'opacity')):
        raise ValueError('Invalid layout numbers')
    return data


def read_remote():
    """Blocking HTTP call, executed in a worker thread by TimerFeed.

    Only a small subset of tournament data is sent to our local OBS clients.
    """
    req = urlrequest.Request(TIMER_URL,
        headers={'Accept': 'application/json', 'User-Agent': 'HI-JACK-LIVE-TIMER-OVERLAY/0.2'})
    with urlrequest.urlopen(req, timeout=TIMEOUT_SEC) as response:
        if response.status != 200:
            raise ValueError('Timer returned non-200 status')
        content = response.read(MAX_RESPONSE + 1)
    if len(content) > MAX_RESPONSE:
        raise ValueError('Unexpected oversized timer response')
    source = json.loads(content.decode('utf-8'))
    if not isinstance(source, dict):
        raise ValueError('Invalid timer response')
    status = source.get('status')
    kind = source.get('kind')
    if status not in ('running', 'paused', 'stopped', 'finished', 'idle', 'ready'):
        raise ValueError('Unexpected timer status')
    if kind not in ('level', 'break', 'gap'):
        raise ValueError('Unexpected timer kind')
    remaining = source.get('remaining_sec')
    if not isinstance(remaining, (float, int)) or isinstance(remaining, bool) or not math.isfinite(remaining):
        raise ValueError('Invalid timer remaining_sec')
    number = source.get('current_level_number', 0)
    if not isinstance(number, int):
        raise ValueError('Invalid level number')
    result = {'status': status, 'kind': kind,
              'remaining_sec': max(0, min(int(remaining), 24*60*60)),
              'level': max(0, min(number, 999)),
              'label': str(source.get('label') or '')[:80],
              'server_time': source.get('server_time')}
    if kind == 'level':
        for key in ('sb', 'bb', 'ante'):
            v = source.get(key)
            if not isinstance(v, (float, int)) or isinstance(v, bool) or not math.isfinite(v) or v < 0 or v > 10**12:
                raise ValueError('Invalid timer blind: ' + key)
            result[key] = int(v)
    return result


class TimerFeed:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.checked_at = 0.0
        self.last_good_at = 0.0
        self.cached = {'connected': False, 'state': None}

    async def read(self):
        async with self.lock:
            now = time.monotonic()
            if now - self.checked_at < SAMPLE_SEC and self.checked_at:
                return copy.deepcopy(self.cached)
            self.checked_at = now
            try:
                state = await asyncio.to_thread(read_remote)
                self.last_good_at = time.monotonic()
                self.cached = {'connected': True, 'state': state}
            except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                log.warning('Timer unreachable: %s', type(exc).__name__)
                # Fail closed: NEVER run a stale countdown when live timer is unreachable.
                self.cached = {'connected': False, 'state': None}
            return copy.deepcopy(self.cached)


class TimerService:
    def __init__(self, storage):
        self.storage = storage

    def read_config(self):
        current = self.storage.get('configuration', initial_config())
        if not isinstance(current, dict):
            return initial_config()
        try:
            base = initial_config()
            if isinstance(current.get('published'), dict):
                for k in PROFILE_IDS:
                    if isinstance(current['published'].get(k), dict):
                        base['published'][k] = normalize_layout(current['published'][k])
            if isinstance(current.get('drafts'), dict):
                for k in PROFILE_IDS:
                    if isinstance(current['drafts'].get(k), dict):
                        base['drafts'][k] = normalize_layout(current['drafts'][k])
            base['revision'] = int(current.get('revision', 0))
            return base
        except (ValueError, TypeError, KeyError):
            return initial_config()

    def set_draft(self, profile, layout):
        cfg = self.read_config()
        cfg['drafts'][profile] = normalize_layout(layout)
        self.storage.set('configuration', cfg)
        return cfg

    def publish(self, profile):
        cfg = self.read_config()
        if profile in cfg['drafts']:
            cfg['published'][profile] = cfg['drafts'].pop(profile)
            cfg['revision'] += 1
            self.storage.set('configuration', cfg)
        return cfg

    def discard(self, profile):
        cfg = self.read_config()
        cfg['drafts'].pop(profile, None)
        self.storage.set('configuration', cfg)
        return cfg


class Plugin:
    def self_check(self):
        return valid_profile('top') == 'top' and normalize_layout(DEFAULT_LAYOUT)['width'] == .285

    def register(self, app, ctx, folder: Path):
        ui = folder / 'frontend'
        app.mount('/module-assets/hj.timer_overlay', StaticFiles(directory=ui), name='timer-overlay-static')
        store = TimerService(ctx.storage())
        feed = TimerFeed()
        ctx.register_service('timer_overlay.api', store)
        ctx.register_ui('Блайнды и таймер', '/timer-control')
        # Exposed only for deterministic in-memory tests (not an HTTP endpoint).
        app.state.hj_timer_feed = feed

        async def auth(request: Request):
            return await ctx.admin_only(request)

        @app.get('/timer-control')
        def timer_admin():
            return FileResponse(ui / 'editor.html')

        @app.get('/overlay/timer')
        def timer_overlay():
            return FileResponse(ui / 'overlay.html')

        @app.get('/api/hj-timer/state')
        async def timer_state():
            return await feed.read()

        @app.get('/api/hj-timer/layout')
        def published_layout(profile: str = Query(default='top')):
            profile = valid_profile(profile)
            return {'profile': profile, 'layout': store.read_config()['published'][profile]}

        @app.get('/api/hj-timer/config', dependencies=[Depends(auth)])
        def config():
            return store.read_config()

        @app.put('/api/hj-timer/draft/{profile}', dependencies=[Depends(auth)])
        def draft(profile: str, payload: LayoutInput):
            return store.set_draft(valid_profile(profile), payload.model_dump())

        @app.post('/api/hj-timer/publish/{profile}', dependencies=[Depends(auth)])
        def publish(profile: str):
            return store.publish(valid_profile(profile))

        @app.post('/api/hj-timer/discard/{profile}', dependencies=[Depends(auth)])
        def discard(profile: str):
            return store.discard(valid_profile(profile))


def create_plugin():
    return Plugin()
