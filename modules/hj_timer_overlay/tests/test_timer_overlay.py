"""Run from module root: python -m unittest discover -s tests -v.

Requires host requirements (FastAPI/Pydantic), but no network access.
"""
import asyncio
import io
import json
import unittest
from unittest.mock import patch

try:
    from backend import plugin
except ModuleNotFoundError:
    from modules.hj_timer_overlay.backend import plugin


class FakeResponse:
    status = 200
    def __init__(self, body):
        self.body = json.dumps(body).encode('utf-8')
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.body[:n]


class TimerContractTests(unittest.TestCase):
    def test_source_parsed(self):
        value={'status':'running','kind':'level','remaining_sec':460,'current_level_number':5,
               'label':'Level 5','sb':300,'bb':600,'ante':600,'server_time':123.0,'secret':'omit'}
        with patch.object(plugin.urlrequest,'urlopen',return_value=FakeResponse(value)) as request:
            data=plugin.read_remote()
        self.assertEqual(data['bb'],600)
        self.assertNotIn('secret',data)
        self.assertEqual(request.call_args.args[0].full_url,'https://timer.hijackpoker.ru/api/state')

    def test_paused(self):
        value={'status':'paused','kind':'level','remaining_sec':440,'current_level_number':5,
               'sb':300,'bb':600,'ante':600}
        with patch.object(plugin.urlrequest,'urlopen',return_value=FakeResponse(value)):
            self.assertEqual(plugin.read_remote()['status'],'paused')

    def test_break(self):
        value={'status':'running','kind':'break','remaining_sec':301,'current_level_number':5,
               'label':'Break'}
        with patch.object(plugin.urlrequest,'urlopen',return_value=FakeResponse(value)):
            self.assertNotIn('sb',plugin.read_remote())

    def test_invalid_values_refused(self):
        value={'status':'running','kind':'level','remaining_sec':'bad','current_level_number':5,
               'sb':300,'bb':600,'ante':600}
        with patch.object(plugin.urlrequest,'urlopen',return_value=FakeResponse(value)):
            with self.assertRaises(ValueError):plugin.read_remote()

    def test_no_stale_after_disconnect(self):
        feed=plugin.TimerFeed()
        data={'status':'running','kind':'level','remaining_sec':55,'sb':200,'bb':400,'ante':400}
        with patch.object(plugin,'read_remote',return_value=data):
            self.assertTrue(asyncio.run(feed.read())['connected'])
        feed.checked_at=0
        with patch.object(plugin,'read_remote',side_effect=OSError('offline')):
            self.assertEqual(asyncio.run(feed.read()),{'connected':False,'state':None})

    def test_layout_bounds(self):
        self.assertEqual(plugin.normalize_layout(plugin.DEFAULT_LAYOUT)['x'],.5)
        with self.assertRaises(Exception):
            plugin.normalize_layout({**plugin.DEFAULT_LAYOUT,'x':-100})
        with self.assertRaises(Exception):
            plugin.normalize_layout({**plugin.DEFAULT_LAYOUT,'variant':'bad'})


if __name__=='__main__':unittest.main()
