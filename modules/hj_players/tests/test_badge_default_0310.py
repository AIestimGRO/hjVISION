"""Module-only regression tests: standard badge preset is visual only."""
from hj_players.backend.rules import (default_placement, badge_visual_settings, configured_default_placement, ensure_placements)

def test_badge_default_excludes_location_and_visibility():
    p = default_placement(1, 'top')
    p.update(width=.14,height=.135,scale=1,font_size=31,padding=40,glow=.7,rotation=-90,opacity=1,visible=False,x=.45,y=.77)
    settings = badge_visual_settings(p)
    assert settings['rotation'] == -90 and settings['font_size'] == 31
    assert 'x' not in settings and 'y' not in settings and 'visible' not in settings

def test_new_players_inherit_saved_default_only():
    from hj_players.backend.rules import initial_state
    s=initial_state()
    s['settings']['badge_default'] = {'width':.14,'height':.135,'font_size':31,'padding':40,'glow':.7,'rotation':-90}
    p={'id':'player-x','seat':4,'is_dealer':False}
    ensure_placements(s,p)
    for profile in s['profiles']:
        v=s['profiles'][profile]['placements']['player-x']
        assert v['rotation']==-90 and v['font_size']==31 and v['padding']==40
        assert (v['x'],v['y']) != (.5,.5)
    ensure_placements(s,{'id':'dealer','seat':None,'is_dealer':True})
    assert s['profiles']['top']['placements']['dealer']['rotation']==0

def test_default_badge_buttons_present():
    html=(__import__('pathlib').Path(__file__).resolve().parents[1]/'frontend/admin.html').read_text(encoding='utf-8')
    js=(__import__('pathlib').Path(__file__).resolve().parents[1]/'frontend/admin.js').read_text(encoding='utf-8')
    for id in ('saveBadgeDefault','applyBadgeDefault','resetBadgeSize'):
        assert 'id="'+id+'"' in html and "$('"+id+"')" in js
    assert '/api/players/default-badge' in js and 'apply-badge-default' in js
