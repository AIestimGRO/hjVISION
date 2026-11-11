"""Offline ZIP validation, safe filesystem swapping and rollback. Trusted packages only."""
from __future__ import annotations
import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime,timezone
from pathlib import Path, PurePosixPath
from uuid import uuid4
from .module_loader import check_manifest, probe_module

MAX_ZIP_BYTES=60*1024*1024
MAX_UNPACKED=100*1024*1024
MAX_FILES=1000

class PackageError(ValueError):pass

class UpdateManager:
    def __init__(self,modules_dir:Path,data_dir:Path):
        self.modules_dir=Path(modules_dir)
        self.data_dir=Path(data_dir)
        self.update_root=self.data_dir/'updates'
        self.backup_root=self.data_dir/'module_backups'

    def extract_verified(self, payload:bytes):
        if len(payload)>MAX_ZIP_BYTES or not payload:raise PackageError('ZIP too large or empty')
        self.update_root.mkdir(parents=True,exist_ok=True)
        staging=Path(tempfile.mkdtemp(prefix='hj-stage-',dir=self.update_root))
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries=[f for f in archive.infolist() if not f.is_dir()]
                if len(entries)>MAX_FILES or sum(f.file_size for f in entries)>MAX_UNPACKED:
                    raise PackageError('ZIP exceeds safe extraction limits')
                names=set();folders=set()
                for info in archive.infolist():
                    if '\\' in info.filename:raise PackageError('Windows path separator forbidden')
                    path=PurePosixPath(info.filename)
                    if path.is_absolute() or '..' in path.parts or not path.parts or any(p in ('.','') for p in path.parts):
                        raise PackageError('Unsafe ZIP path')
                    forbidden=set('<>:"\\|?*')
                    if any(any(c in forbidden for c in piece) or piece.endswith(('.', ' ')) or
                           piece.upper().split('.')[0] in ('CON','PRN','AUX','NUL','COM1','LPT1')
                           for piece in path.parts):
                        raise PackageError('Forbidden Windows filename in ZIP')
                    if len(path.parts)<2 or not path.parts[0].startswith('hj_'):
                        raise PackageError('ZIP must contain one hj_* module folder')
                    folders.add(path.parts[0]);name=path.as_posix().rstrip('/')
                    if name in names:raise PackageError('Duplicate file in ZIP')
                    names.add(name)
                    mode=(info.external_attr>>16)
                    if stat.S_ISLNK(mode):raise PackageError('Symlinks are forbidden')
                    if len(info.filename)>255 or info.file_size>20*1024*1024:
                        raise PackageError('Invalid path or oversized file')
                    if info.is_dir():continue
                    dest=staging.joinpath(*path.parts)
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    # Extract each file under controlled, freshly created staging dir.
                    with archive.open(info) as inp, dest.open('wb') as out:shutil.copyfileobj(inp,out)
                if len(folders)!=1:raise PackageError('Only one module per ZIP is allowed')
            folder=staging/next(iter(folders))
            self.check_checksums(folder)
            manifest=probe_module(folder)
            if not manifest['enabled']:raise PackageError('Disabled module cannot be installed as update')
            return staging, folder, manifest
        except Exception:
            shutil.rmtree(staging,ignore_errors=True)
            raise

    @staticmethod
    def check_checksums(folder):
        p=folder/'checksums.json'
        if not p.is_file():raise PackageError('checksums.json missing')
        data=json.loads(p.read_text(encoding='utf8'))
        if not isinstance(data,dict):raise PackageError('Invalid checksums')
        actual={f.relative_to(folder).as_posix() for f in folder.rglob('*') if f.is_file() and f.name!='checksums.json'}
        if actual != set(data):raise PackageError('File list does not match checksums.json')
        for path,expected in data.items():
            if not isinstance(expected,str) or len(expected)!=64 or hashlib.sha256((folder/path).read_bytes()).hexdigest()!=expected:
                raise PackageError('SHA256 checksum mismatch: '+str(path))

    def validate(self,payload:bytes):
        stage,folder,manifest=self.extract_verified(payload)
        try:return {'ok':True,'id':manifest['id'],'version':manifest['version'],
                   'host_api':manifest['host_api'], 'requires':manifest['requires'], 'name':manifest['name'],
                   'changelog':(folder/'CHANGELOG.md').read_text(encoding='utf8')[:4000] if (folder/'CHANGELOG.md').exists() else ''}
        finally:shutil.rmtree(stage,ignore_errors=True)

    def install(self,payload:bytes,known_capabilities:set):
        stage,folder,manifest=self.extract_verified(payload)
        mid=manifest['id'];target=self.modules_dir/folder.name
        try:
            missing=set(manifest['requires'])-known_capabilities-set(manifest['provides'])
            if missing:raise PackageError('Unsatisfied dependencies: '+', '.join(sorted(missing)))
            old=check_manifest(target) if target.exists() else None
            if old and old['id']!=mid:raise PackageError('Wrong module identity')
            self.modules_dir.mkdir(parents=True,exist_ok=True)
            backup=None
            if target.exists():
                dest=self.backup_root/folder.name
                dest.mkdir(parents=True,exist_ok=True)
                backup=dest/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'-'+uuid4().hex[:6])
                os.replace(target,backup)
            try:
                os.replace(folder,target)
                probe_module(target)
            except Exception:
                if target.exists():shutil.rmtree(target,ignore_errors=True)
                if backup:os.replace(backup,target)
                raise
            return {'ok':True,'id':mid,'version':manifest['version'],'backup':bool(backup),'restart_required':True}
        finally:shutil.rmtree(stage,ignore_errors=True)

    def rollback(self,mid:str):
        if not isinstance(mid,str) or not mid.startswith('hj.') or '/' in mid or '\\' in mid:
            raise PackageError('Invalid module id')
        name=mid.replace('.','_')
        src=self.backup_root/name
        if not src.exists():raise PackageError('No previous version available')
        options=sorted((d for d in src.iterdir() if d.is_dir()),reverse=True)
        if not options:raise PackageError('No previous version available')
        previous=options[0]
        previous_manifest=probe_module(previous)
        if previous_manifest['id']!=mid:raise PackageError('Mismatched backup id')
        target=self.modules_dir/name
        swap=src/('replaced-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
        if target.exists():os.replace(target,swap)
        try:os.replace(previous,target)
        except Exception:
            if swap.exists():os.replace(swap,target)
            raise
        return {'ok':True,'id':mid,'version':previous_manifest['version'],'restart_required':True}


def write_checksums(folder:Path):
    hashes={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*'))
            if p.is_file() and p.name!='checksums.json' and p.suffix!='.pyc' and
            not {'__pycache__','.pytest_cache'}.intersection(p.relative_to(folder).parts)}
    (folder/'checksums.json').write_text(json.dumps(hashes,indent=2,ensure_ascii=False),encoding='utf8')
    return hashes
