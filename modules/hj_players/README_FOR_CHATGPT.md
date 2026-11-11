# Instructions for updating HJ Players in a separate ChatGPT conversation

Module ID: `hj.players`. Version: `0.3.9`. CORE public API: `1.x`.
Status: working.

## Responsibilities and files
- `backend/plugin.py`: entrypoint `create_plugin()` -> `Plugin.register(app, ctx, folder)` and `self_check()`.
- `frontend/`: browser UI/overlays and local scripts/styles (when present).
- `backend/rules.py` in hj_players: independent player validation helpers and shape of published placement data.
- `assets/`: local graphics and sounds (when present).
- `contracts/`: public API and events. `module.json`: capabilities, permissions and version.
- `tests/`: module-specific regression and contract tests.
- `migrations/`: versioned data migrations when needed.

## Public Host API
Use `ctx.state()` to read a COPY; `await ctx.change(mutator)` for atomic state updates;
`ctx.get_service(name)` / `ctx.register_service(name, impl)` for capabilities;
`ctx.events.subscribe(event, handler)` and `await ctx.events.publish(event,payload)`;
`ctx.storage().get/set/delete` for private module data; `ctx.register_ui(title,path)` for navigation.
Authorization is `Depends(ctx.admin_only)` for write endpoints.
Do NOT import another module's Python files. Keep existing public HTTP endpoints and WS event formats.

## Data
Current player/overlay state uses the v0.2-compatible CORE SQLite snapshot format,
external to module folder. New module-specific data must use `ctx.storage()`.
Never package real user databases, API keys, personal statistics, passwords or secret files.

## Modification rules
Edit only the files inside THIS ZIP. Do not modify published `module.json.id`,
`provides`, `requires`, version of `host_api`, existing HTTP/WS contracts without a
separate coordinated migration. Increment SemVer and update `CHANGELOG.md`, docs and tests.

## Local testing and reinstall
If only this folder is available: run `python -m pytest tests -q` (with FastAPI/Pydantic installed), then `python tools/build_zip.py`.
In the full app repo, also run `python -m pytest -q`.
The ZIP must have `hj_*/module.json` plus `checksums.json`.
Go to `http://127.0.0.1:8765/modules`, first Validate ZIP then Install ZIP;
installation is refused while an overlay connects, restart app afterwards.
Rollback: same screen -> Rollback; persistent SQLite data is not inside module folder.
No new third-party imports unless dependencies are bundled with a compatible Windows build.

## Self-contained ZIP packaging contract
Run the included `tools/build_zip.py` from a directory containing this one
module folder. It regenerates `checksums.json` with SHA256 for EVERY file except
itself, and outputs a ZIP containing exactly `hj_module_name/...` paths. A new
ChatGPT conversation can perform this using Python with only the supplied ZIP.
If the public contract or CORE host API must change, stop: explain the need for
an explicit coordinated upgrade. Never silently change another module.

### Desktop v0.3.1 integration
The players admin page displays the optional `quitDesktop` control only when hosted in a native pywebview window. It calls the window-owned `pywebview.api.quit` bridge; normal browser access does not show this control. Never store secrets in the module.

### WebView2 stability (v0.3.2)
The player modal has no full-screen backdrop-filter and input focus is deferred one animation frame. The submit button is disabled while the add/edit/replace API request is in progress; do not remove this guard. Core introduces a 10-second request deadline and UI diagnostics at /api/desktop/client-error and /api/desktop/heartbeat.

### Edge app mode v0.3.5
The same quitDesktop control becomes visible in Edge --app mode only after GET /api/desktop/edge-session returns edge_app=true. A fresh nonce in its response is required in X-HJ-Desktop-Token for POST /api/desktop/edge-quit. The endpoint is present only in the Edge launcher runtime (not in ordinary browser diagnostic mode) and requests local-origin access. This keeps the module portable, avoids coupling to Windows APIs, and stops the OBS server only after an explicit operator confirmation.

### HJ PLAYERS v0.3.6 positioning and operator workflow
- When an existing player without a seat is assigned their **first** seat, untouched default-center x/y in each profile are set to the correct seat coordinates. Any manual x/y placement is preserved. Subsequent seat changes do not move badges automatically.
- To repair existing seat-assigned players already overlapping at the center, choose **РЕДАКТОР**, press **Расставить по боксам**. This changes only the selected camera profile DRAFT; published positions stay live in OBS until **Опубликовать в OBS** is pressed.
- For side seating, select a badge; press **−90°**, **0°** or **+90°** under Properties. This rotates the entire badge, including player name, and can also be fine-adjusted with the rotation slider. Publish before expecting OBS to update.
- Publishing now awaits any draft save, reads pending layout from API, issues publish, compares result with expected persisted positions, and reports an error instead of false success if mismatched. Switching back to live prompts for publication if a draft exists.
- To install standalone ZIP: close OBS or disconnect browser overlays (installation is refused while connected), visit `/modules`, validate the signed-by-checksum ZIP, confirm installation, restart app. Keep rollback available. Do not update GitHub stable releases until Windows physical verification by the user.
- Existing endpoints remain compatible. New endpoint: `POST /api/profiles/{profile_id}/auto-place` (admin required) writes DRAFT only and preserves non-positional custom appearance/rotation.


### HJ PLAYERS v0.3.7 camera preview scaling
- Preview editor and OBS Browser Source must both be treated as one 1920×1080 (16:9) coordinate system; player positions remain normalized 0..1, no schema change.
- In editor mode the dashboard's large camera stage expands to available width by default; button «Широкий кадр» toggles this locally. Live mode keeps the compact dashboard.
- The camera screenshot uploaded using «Загрузить кадр OBS» is purely an *editor-local* preview background, never broadcast or stored in SQLite. Always capture a FULL 16:9 OBS scene frame; uploaded cropped screenshots are letterboxed to 16:9 with a warning. This avoids silent image cropping or inaccurate overlays.
- For exact OBS alignment set OBS Canvas 1920×1080, Camera Source fit to scene (ensure no extra crop/transform), and both Browser Sources width=1920 height=1080 filling the same scene. A different camera crop/letterboxing requires matching the actual OBS full scene screenshot.
- Do not pack operators' real camera screenshots in the module ZIP; they remain private, local browser data.

### HJ PLAYERS 0.3.9 quick/advanced settings
- Editor UI `frontend/admin.html` displays simple badge rotation and a grip under the camera stage; old sliders are hidden inside «Расширенная» until toggled. Preference stored in `localStorage`.
- Simple mode diagonal grip proportional resizing supports -90/+90° orientation. Advanced mode can still adjust width/height independently.
- Font size is automatically scaled from width AND height using `frontend/badge-sizing.js`. The module-local script loads after CORE `common.js` in both `admin.html` and `players.html`, ensuring pixel parity in OBS. The historical `font_size` field is a base font value, not a fixed rendered pixel size. No CORE changes required.
- To modify later: keep script included in both HTML pages; never edit CORE common.js in a standalone ZIP update.
