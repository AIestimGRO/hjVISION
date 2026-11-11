# HJ TIMER OVERLAY — Self-contained module for ChatGPT

Module: hj.timer_overlay; folder: hj_timer_overlay; version: 0.1.0; Host API: 1.x.

Entry: `backend/plugin.py:create_plugin`, frontend files in `frontend/`. The only external upstream endpoint is fixed in code `https://timer.hijackpoker.ru/api/state`, fetched through stdlib HTTPS in a worker thread and cached for 1.5 seconds with 2.5s timeout.

Public local GET APIs: `/api/hj-timer/state` (sanitized remote feed), `/api/hj-timer/layout?profile=top|side|extra` (published-only). Admin token required for `/api/hj-timer/config`, PUT `/api/hj-timer/draft/{profile}`, POST `/api/hj-timer/publish/{profile}`, POST `/api/hj-timer/discard/{profile}`. Editing UI `/timer-control`, transparent OBS UI `/overlay/timer?layout=top|side|extra`.

Storage via `ctx.storage()` namespaced sqlite in user data (not replaceable module directory). OBS client polls upstream only through local CORE; no CORS or direct network in OBS. The feed is read-only and doesn't alter the remote tournament timer. On network failure, no stale running countdown. Endpoint forbids user-supplied URLs. Timer panel supports 16:9 normalized x/y positions and multiple profiles.

For future changes, preserve module.json contracts, checksums.json, tests and readme. To update, submit only this folder zipped with checksums.json via HI, JACK LIVE module installer. Never edit other modules for timer changes. Do not publish an untested version as stable to GitHub without physical operator approval.
