"""Standalone deterministic module ZIP builder: no CORE or internet needed.
Run: python tools/build_zip.py from an extracted hj_* module folder.
"""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if not re.fullmatch(r'hj_[a-z][a-z0-9_]+',ROOT.name):raise SystemExit('Expected hj_* module folder')
manifest=json.loads((ROOT/'module.json').read_text(encoding='utf8'))
version=manifest['version']
files={}
for p in sorted(ROOT.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(ROOT).as_posix()
    if '__pycache__' in rel or '.pytest_cache' in rel or p.name=='checksums.json' or p.suffix in ('.pyc','.sqlite3'):
        continue
    files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'checksums.json').write_text(json.dumps(files,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
out=ROOT.parent/(ROOT.name+'-v'+version+'.zip')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
    for rel in list(files)+['checksums.json']:
        z.write(ROOT/rel,arcname=ROOT.name+'/'+rel)
print(out)
