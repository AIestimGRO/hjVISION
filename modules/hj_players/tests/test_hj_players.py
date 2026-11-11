"""Smoke test that runs from ONLY this module ZIP (with project Python dependencies)."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
from hj_players.backend.plugin import create_plugin

def test_plugin_entrypoint():
    assert create_plugin().self_check() is True

def test_bundle_is_self_describing():
    import json
    data=json.loads((ROOT/'module.json').read_text(encoding='utf8'))
    assert data['id']=='hj.players'
    assert data['host_api']=='1.x'
    assert (ROOT/'README_FOR_CHATGPT.md').exists()
    assert (ROOT/'contracts/API.md').exists()
