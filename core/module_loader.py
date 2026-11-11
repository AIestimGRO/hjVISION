"""Load and validate external modules with versioned contracts (no hard-coded module list)."""
from __future__ import annotations
import importlib.util
import json
import logging
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from .runtime import HOST_API_VERSION
from .migrations import apply_migrations
log=logging.getLogger('hijack.modules')
PERMISSIONS={'state.read','state.write','storage.module','events.read','events.write',
             'services.provide','services.consume','ui.register','obs.read','obs.write'}
IDENT=re.compile(r'^hj\.[a-z][a-z0-9_]{1,50}$')
FOLDER=re.compile(r'^hj_[a-z][a-z0-9_]{1,50}$')
VERSION=re.compile(r'^\d+\.\d+\.\d+$')
ENTRY=re.compile(r'^backend\.[a-z_][a-z0-9_.]*:[a-z_][a-z0-9_]*$')

@dataclass
class ModuleRecord:
    manifest:dict
    folder:Path
    status:str='ready'
    error:str=''


def check_manifest(folder:Path)->dict:
    path=folder/'module.json'
    if not path.is_file():raise ValueError('module.json missing')
    raw=path.read_bytes()
    if len(raw)>64*1024:raise ValueError('Oversized module.json')
    manifest=json.loads(raw.decode('utf-8'))
    if not isinstance(manifest,dict):raise ValueError('module.json must be an object')
    required={'id','name','version','host_api','entrypoint','provides','requires','optional','permissions','enabled'}
    if not required <= manifest.keys():raise ValueError('Required module.json fields missing: '+str(required-manifest.keys()))
    ident=manifest['id']
    if not isinstance(ident,str) or not IDENT.fullmatch(ident) or (folder.name != ident.replace('.','_') and folder.parent.name != ident.replace('.','_')):
        raise ValueError('Module ID does not match folder')
    if not isinstance(manifest['version'],str) or not VERSION.fullmatch(manifest['version']):raise ValueError('Invalid SemVer')
    host=manifest['host_api']
    if host not in ('1.x',HOST_API_VERSION):raise ValueError('Incompatible host API '+str(host))
    if not isinstance(manifest['enabled'],bool):raise ValueError('Invalid enabled field')
    if not isinstance(manifest['name'],str) or not manifest['name'] or len(manifest['name'])>100:
        raise ValueError('Invalid module name')
    if not isinstance(manifest['entrypoint'],str) or not ENTRY.fullmatch(manifest['entrypoint']):
        raise ValueError('Invalid entrypoint')
    for attr in ('provides','requires','optional','permissions'):
        values=manifest[attr]
        if not isinstance(values,list) or any(not isinstance(s,str) or len(s)>100 for s in values) or len(set(values))!=len(values):
            raise ValueError('Invalid '+attr)
    if not set(manifest['permissions'])<=PERMISSIONS:raise ValueError('Unknown permission')
    schema=manifest.get('data_schema',0)
    if not isinstance(schema,int) or isinstance(schema,bool) or not 0<=schema<=9999:raise ValueError('Invalid data_schema')
    for relative in ('README.md','README_FOR_CHATGPT.md','CHANGELOG.md','contracts/API.md','contracts/EVENTS.md','docs/INTEGRATION.md'):
        if not (folder/relative).is_file():raise ValueError('Missing required documentation '+relative)
    return manifest


def plugin_factory(folder:Path, entrypoint:str):
    """Python package import from a selected folder, supporting local relative imports.
    Each import uses a fresh namespace, including while preflighting staged updates.
    """
    module_name, factory_name=entrypoint.split(':',1)
    prefix='hj_pkg_'+uuid4().hex
    segments=module_name.split('.')
    chain=[prefix]+segments
    for i in range(1,len(chain)):
        pkg='.'.join(chain[:i])
        package_dir=folder.joinpath(*segments[:i-1])
        obj=types.ModuleType(pkg)
        obj.__path__=[str(package_dir)]
        obj.__package__=pkg
        sys.modules[pkg]=obj
    target=folder.joinpath(*segments).with_suffix('.py')
    if not target.is_file():raise ValueError('Missing plugin entrypoint '+str(target))
    name='.'.join(chain)
    spec=importlib.util.spec_from_file_location(name,target)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    old_bytecode=sys.dont_write_bytecode
    sys.dont_write_bytecode=True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode=old_bytecode
    factory=getattr(module,factory_name,None)
    if not callable(factory):raise ValueError('Plugin entrypoint is not callable')
    return factory


def probe_module(folder:Path):
    manifest=check_manifest(folder)
    if not manifest['enabled']:return manifest
    factory=plugin_factory(folder,manifest['entrypoint'])
    plugin=factory()
    if not callable(getattr(plugin,'register',None)):raise ValueError('Plugin.register missing')
    smoke=getattr(plugin,'self_check',None)
    if smoke and smoke() is not True:raise ValueError('Plugin.self_check failed')
    return manifest

class ModuleLoader:
    def __init__(self,root:Path,data_dir:Path):
        self.root=Path(root)
        self.data_dir=Path(data_dir)
        self.records={}
        self.capabilities={'core.events','core.storage','core.state','core.ui','core.api'}

    def disabled_ids(self):
        p=self.data_dir/'disabled_modules.json'
        try:
            disabled=json.loads(p.read_text(encoding='utf8'))
            return set(disabled) if isinstance(disabled,list) else set()
        except (FileNotFoundError,ValueError):return set()

    def set_disabled(self,module_id,disabled):
        current=self.disabled_ids()
        if disabled:current.add(module_id)
        else:current.discard(module_id)
        self.data_dir.mkdir(parents=True,exist_ok=True)
        p=self.data_dir/'disabled_modules.json'
        tmp=p.with_suffix('.tmp')
        tmp.write_text(json.dumps(sorted(current)),encoding='utf8')
        tmp.replace(p)

    def discover(self):
        self.records={}
        if not self.root.is_dir():return
        disabled=self.disabled_ids()
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir() or not FOLDER.fullmatch(folder.name):continue
            try:
                manifest=check_manifest(folder)
                status='disabled' if not manifest['enabled'] or manifest['id'] in disabled else 'ready'
                self.records[manifest['id']]=ModuleRecord(manifest,folder,status)
            except Exception as exc:
                log.warning('Module %s ignored: %s',folder,exc)
                # invalid manifests cannot be trusted as module IDs

    def register(self,app,host):
        self.discover()
        pending={m for m,r in self.records.items() if r.status=='ready'}
        while pending:
            progress=False
            for ident in sorted(pending):
                record=self.records[ident]
                required=set(record.manifest['requires'])
                if not required<=self.capabilities:continue
                try:
                    plugin=plugin_factory(record.folder,record.manifest['entrypoint'])()
                    if callable(getattr(plugin,'self_check',None)) and plugin.self_check() is not True:
                        raise ValueError('Self-test failed')
                    apply_migrations(self.data_dir, record.folder, record.manifest)
                    ctx=host.context(ident,record.manifest['permissions'])
                    plugin.register(app,ctx,record.folder)
                    # A declared public service must actually be registered.
                    for capability in record.manifest['provides']:
                        if capability.endswith('.api') and capability not in host.services:
                            raise ValueError('Declared service not registered: '+capability)
                    record.status='loaded'
                    self.capabilities.update(record.manifest['provides'])
                except Exception as exc:
                    record.status='error';record.error=str(exc)
                    log.exception('Failed loading %s',ident)
                pending.remove(ident);progress=True
            if not progress:
                for ident in pending:
                    record=self.records[ident]
                    record.status='error';record.error='Missing dependencies: '+', '.join(sorted(set(record.manifest['requires'])-self.capabilities))
                break
        return self.records

    def public_status(self):
        return [{'id':m.manifest['id'],'name':m.manifest['name'],'version':m.manifest['version'],
                 'host_api':m.manifest['host_api'],'status':m.status,'error':m.error,
                 'requires':m.manifest['requires'],'provides':m.manifest['provides']}
                for m in self.records.values()]
