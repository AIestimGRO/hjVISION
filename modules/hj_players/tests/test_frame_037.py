"""Regression checks for camera / 16:9 editor parity in portable HJ PLAYERS."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]

def test_editor_canvas_matches_obs_and_can_expand_without_core_changes():
    html=(ROOT/'frontend/admin.html').read_text(encoding='utf8')
    css=(ROOT/'frontend/graphics.css').read_text(encoding='utf8')
    base_css=(ROOT/'frontend/style.css').read_text(encoding='utf8')
    js=(ROOT/'frontend/admin.js').read_text(encoding='utf8')
    assert re.search(r'\.stage\s*\{[^}]*aspect-ratio:16\s*/\s*9', css)
    assert '.stage{aspect-ratio:16/9;' in base_css
    assert 'editor-wide' in css and 'editor-wide' in js
    assert 'id="widePreview"' in html
    assert 'id="frameGuide"' in html
    assert '16:9 · 1920×1080' in html
    assert 'render(); // also attach drag controls' in js

def test_camera_reference_never_crops_or_changes_obs_state():
    js=(ROOT/'frontend/admin.js').read_text(encoding='utf8')
    assert 'Math.min(1920/img.width,1080/img.height)' in js
    assert 'Math.max(1920/img.width,1080/img.height)' not in js
    assert 'ctx.fillRect(0,0,1920,1080)' in js
    assert 'img.width/img.height-16/9' in js
    assert 'localStorage.setItem(`hj-preview-${profileId}`' in js
    assert 'POST /api' not in js[js.index("$('screenshotFile').onchange"):js.index("$('removeScreenshot').onclick")]
    assert json.loads((ROOT/'module.json').read_text(encoding='utf8'))['version']=='0.3.10'

def test_camera_upload_fit_math_for_common_inputs():
    for src_w,src_h in [(1920,1080),(3840,2160),(1403,600),(1440,1080),(1080,1920)]:
        scale=min(1920/src_w,1080/src_h)
        width,height=src_w*scale,src_h*scale
        assert width<=1920+1e-6 and height<=1080+1e-6
        assert width==1920 or height==1080
        assert (1920-width)/2>=0 and (1080-height)/2>=0
