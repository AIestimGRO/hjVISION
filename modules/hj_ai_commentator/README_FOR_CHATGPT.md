# Instructions for updating JACK AI Commentator in a separate ChatGPT conversation

Module ID: `hj.ai_commentator`. Version: `0.1.0` (feature branch). CORE public API: `1.x`.
Status: disabled-by-default offline template preview prototype; not an AI commentator, no TTS, OBS output or Training Sync.

## Responsibilities and files
- `backend/plugin.py`: entrypoint `create_plugin()` -> `Plugin.register(app, ctx, folder)` and `self_check()`.
- `frontend/`: browser UI/overlays and local scripts/styles (when present).
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
From app repo: `python -m pytest -q` and `python scripts/package_module.py hj_ai_commentator`.
The ZIP must have `hj_*/module.json` plus `checksums.json`.
Go to `http://127.0.0.1:8765/modules`, first Validate ZIP then Install ZIP;
installation is refused while an overlay connects, restart app afterwards.
Rollback: same screen -> Rollback; persistent SQLite data is not inside module folder.
No new third-party imports unless dependencies are bundled with a compatible Windows build.

## Current state
Version 0.1.0 has a confirmation-gated offline template preview endpoint and tests; full AI functionality remains unimplemented.
