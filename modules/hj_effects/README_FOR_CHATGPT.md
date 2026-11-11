# Instructions for updating HJ Effects in a separate ChatGPT conversation

Module ID: `hj.effects`. Version: `0.3.0`. CORE public API: `1.x`.
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
