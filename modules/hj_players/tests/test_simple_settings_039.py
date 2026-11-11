"""Portable checks for the 0.3.9 module-only quick badge setup."""
from pathlib import Path
from html.parser import HTMLParser

HERE=Path(__file__).resolve().parents[1]/'frontend'

class CollectIds(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])

def test_ui_has_simple_default_full_advanced_options_and_unique_ids():
    page=(HERE/'admin.html').read_text('utf-8')
    ids=CollectIds();ids.feed(page)
    assert len(ids.ids)==len(set(ids.ids)), 'Duplicate HTML IDs break event handlers'
    for key in ('badgeModeBasic','badgeModeAdvanced','badgeAdvancedOptions','propFont','rotateLeft','rotateStraight','rotateRight','resetBadgeSize'):
        assert key in ids.ids
    assert page.index('id="properties"')<page.index('class="panel theme-panel"')
    assert '<div id="badgeAdvancedOptions" class="badge-advanced-options" hidden>' in page
    assert 'id="badgeModeBasic" class="button soft active"' in page
    js=(HERE/'admin.js').read_text('utf-8')
    assert "badgeSettingsMode = localStorage.getItem('hj-badge-settings-mode') === 'advanced' ? 'advanced' : 'basic'" in js
    assert "badgeSettingsMode === 'basic'" in js
    assert 'cornerX * cornerX + cornerY * cornerY' in js
    assert 'Math.round(placement.width * ratio * 10000)' in js

def test_font_autosizing_is_module_local_and_loaded_in_both_uis():
    name='badge-sizing.js'
    script=(HERE/name).read_text('utf-8')
    assert 'HJ.fitBadge = function fitBadgeProportionally' in script
    assert 'HJ.positionBadge = (el, p)' in script
    assert 'Math.sqrt((width / .15) * (height / .065))' in script
    assert 'height * canvas.clientHeight * .65' in script
    for filename in ('admin.html','players.html'):
        page=(HERE/filename).read_text('utf-8')
        assert '/module-assets/hj.players/'+name+'?v=040' in page
        assert page.index('/static/common.js') < page.index(name)
    # This is a standalone HJ PLAYERS ZIP, not an update to CORE.
    assert not (HERE.parents[1]/'core').exists()
