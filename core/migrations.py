"""Versioned, backed-up per-module data migrations (external namespace only)."""
from __future__ import annotations
import importlib.util
import re
import shutil
from datetime import datetime,timezone
from pathlib import Path
from .storage import NamespaceStorage

MIGRATION_RE=re.compile(r'^([0-9]{4})_[a-z0-9_]+\.py$')

def apply_migrations(data_dir:Path, folder:Path, manifest:dict):
    target=manifest.get('data_schema',0)
    if not isinstance(target,int) or target<0 or target>9999:
        raise ValueError('Invalid module data_schema')
    if target==0:return None
    db=NamespaceStorage(Path(data_dir)/'module_data',manifest['id'])
    old=db.get('__schema_version__',0)
    if old>target:raise ValueError('Stored data schema is newer than module')
    if old==target:return None
    candidates={int(m.group(1)):p for p in sorted((folder/'migrations').glob('*.py')) if (m:=MIGRATION_RE.fullmatch(p.name))}
    missing=[i for i in range(old+1,target+1) if i not in candidates]
    if missing:raise ValueError('Missing migrations: '+str(missing))
    backup_dir=Path(data_dir)/'module_data'/'backups'
    backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/(manifest['id']+'-before-v'+str(target)+'-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')+'.sqlite3')
    shutil.copy2(db.path,backup)
    try:
        for index in range(old+1,target+1):
            source=candidates[index]
            spec=importlib.util.spec_from_file_location('hj_migration_'+manifest['id'].replace('.','_')+'_'+str(index),source)
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fn=getattr(mod,'upgrade',None)
            if not callable(fn):raise ValueError('Migration upgrade(storage) missing: '+source.name)
            fn(db)
            db.set('__schema_version__',index)
    except Exception:
        shutil.copy2(backup,db.path)
        raise
    return backup
