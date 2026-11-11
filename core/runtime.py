"""Public Host API 1.x. Modules must never import one another's private implementation."""
from __future__ import annotations
import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException, Request, WebSocket
from .storage import NamespaceStorage

HOST_API_VERSION = '1.0.0'

class EventBus:
    def __init__(self):
        self.subscribers = {}
        self.history = []

    def subscribe(self, event_name, callback):
        self.subscribers.setdefault(event_name, []).append(callback)

    async def publish(self, name, payload, source='core'):
        if not isinstance(name,str) or '.' not in name or not isinstance(payload,dict):
            raise ValueError('Invalid event name/payload')
        event = {'event_id':str(uuid4()), 'schema_version':'1.0', 'type':name,
                 'timestamp':datetime.now(timezone.utc).isoformat(), 'source':source,
                 'payload':copy.deepcopy(payload)}
        self.history.append(event)
        if len(self.history)>100:self.history=self.history[-100:]
        for callback in tuple(self.subscribers.get(name, [])) + tuple(self.subscribers.get('*', [])):
            try:
                result = callback(copy.deepcopy(event))
                if asyncio.iscoroutine(result): await result
            except Exception:
                import logging
                logging.getLogger('hijack.events').exception('Event handler %s failed',name)
        return event

class SocketHub:
    def __init__(self):
        self.connections = {}  # ws -> role

    async def connect(self, ws:WebSocket, snapshot:dict, role:str='admin'):
        await ws.accept()
        role = role if role in ('admin','overlay') else 'admin'
        self.connections[ws] = role
        await ws.send_json({'type':'state','state':copy.deepcopy(snapshot)})

    @property
    def overlays_online(self):
        return sum(role=='overlay' for role in self.connections.values())

    async def broadcast(self, event):
        # Broadcast concurrently. The former sequential loop could stall one
        # mutation for 1.5s * EACH paused OBS/WebView client (10 clients = 15s).
        # One total timeout keeps buttons responsive during an OBS renderer hang.
        clients = tuple(self.connections)
        if not clients:
            return

        async def send_one(ws):
            try:
                await asyncio.wait_for(ws.send_json(event), timeout=1.5)
                return True
            except Exception:
                return False

        delivered = await asyncio.gather(*(send_one(ws) for ws in clients))
        for ws, success in zip(clients, delivered):
            if not success:
                self.connections.pop(ws, None)

class HostRuntime:
    def __init__(self, store, hub, data_dir, token=''):
        self.store=store
        self.hub=hub
        self.data_dir=data_dir
        self.token=token
        self.lock=asyncio.Lock()
        self.events=EventBus()
        self.services={}
        self.registered_ui={}

    async def admin_only(self, request:Request):
        if self.token and request.headers.get('X-HJ-Token') != self.token:
            raise HTTPException(401,'Неверный пароль управления')

    async def change(self, mutator, source='core'):
        async with self.lock:
            next_state=copy.deepcopy(self.store.state)
            try:
                mutator(next_state)
                # SQLite writes may block briefly on Windows antivirus / disk I/O.
                # Keep the HTTP event loop available while the transaction commits.
                state=await asyncio.to_thread(self.store.commit,next_state)
            except ValueError as exc:
                raise HTTPException(400,str(exc)) from exc
            await self.hub.broadcast({'type':'state','state':state})
        await self.events.publish('state.changed',{'revision':state['revision']},source)
        return state

    def context(self, module_id, permissions):
        return ModuleContext(self,module_id,frozenset(permissions))

class ModuleContext:
    """Stable public module Host API. Permissions express intent, not a Python sandbox."""
    def __init__(self, host, module_id, permissions):
        self._host=host
        self.module_id=module_id
        self.permissions=permissions
        self.host_api=HOST_API_VERSION
        self.events=EventBridge(host.events,module_id,permissions)

    def _check(self, permission):
        if permission not in self.permissions:
            raise PermissionError(f'{self.module_id}: missing {permission}')

    def state(self):
        self._check('state.read')
        return copy.deepcopy(self._host.store.state)

    async def change(self, func):
        self._check('state.write')
        return await self._host.change(func, self.module_id)

    async def admin_only(self, request):
        return await self._host.admin_only(request)

    async def broadcast(self, message):
        self._check('events.write')
        await self._host.hub.broadcast(message)

    def register_service(self,name,instance):
        self._check('services.provide')
        if name in self._host.services:raise ValueError(f'Service already registered: {name}')
        self._host.services[name]=instance

    def get_service(self,name):
        self._check('services.consume')
        return self._host.services.get(name)

    @property
    def user_data_dir(self):
        return self._host.data_dir

    def storage(self):
        self._check('storage.module')
        return NamespaceStorage(self._host.data_dir / 'module_data', self.module_id)

    def register_ui(self,title,path):
        self._check('ui.register')
        self._host.registered_ui[self.module_id]={'title':title,'path':path}

class EventBridge:
    def __init__(self,bus,source,permissions):
        self._bus=bus;self._source=source;self._permissions=permissions
    def subscribe(self,name,handler):
        if 'events.read' not in self._permissions:raise PermissionError('events.read permission required')
        return self._bus.subscribe(name,handler)
    async def publish(self,name,payload):
        if 'events.write' not in self._permissions:raise PermissionError('events.write permission required')
        return await self._bus.publish(name,payload,self._source)

