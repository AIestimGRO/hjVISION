# HI, JACK CORE — public Host API 1.0.0

## Stable module lifecycle

CORE discovers `modules/hj_*/module.json`, validates its ID, SemVer, host API, capabilities, permissions and required docs, resolves dependencies, then imports **only** the declared `backend.plugin:create_plugin` factory. `create_plugin()` must return an object implementing:

```python
class Plugin:
    def self_check(self) -> bool: ...
    def register(self, app: FastAPI, ctx: ModuleContext, folder: Path) -> None: ...
```

`ctx` is a restricted convenience interface (not a process sandbox):

| Method / field | Permission | Contract |
|---|---|---|
| `ctx.state()` | `state.read` | Deep-copy of published + draft legacy state v2 |
| `await ctx.change(mutator)` | `state.write` | Atomic validation/commit of shared state and broadcast |
| `await ctx.admin_only(request)` | None | Auth dependency for mutations; requires host admin token if configured |
| `ctx.events.subscribe(name, handler)` | `events.read` | Receive event dict; sync or async handler |
| `await ctx.events.publish(name, payload)` | `events.write` | Create versioned envelope and deliver it |
| `await ctx.broadcast(msg)` | `events.write` | Legacy OBS WebSocket message (`type:state/effect/effect-stop`) |
| `ctx.register_service(name, service)` | `services.provide` | Register public service once |
| `ctx.get_service(name)` | `services.consume` | Resolve public registered service; may be `None` |
| `ctx.storage()` | `storage.module` | Independent SQLite key/value namespace, JSON serializable |
| `ctx.register_ui(title, path)` | `ui.register` | Advertise module UI route |
| `ctx.user_data_dir` | read-only | External user-data root; do not store data in module folder |

All registered routes are served from a single process. External Python modules have full process privileges, so **only trusted packages** should be installed. Declaring permissions documents interface usage but does not sandbox malicious Python code. For untrusted or CPU-heavy future modules, implement a separately constrained worker process.

## Core events v1.0

Envelope: `{ "event_id": uuid, "schema_version": "1.0", "type": "player.added", "timestamp": ISO8601 UTC, "source": "hj.players", "payload": {...} }`. This is an in-memory bus, not durable event queue. Subscribers should be idempotent if they persist effects of events.

Emitted now: `state.changed`, `player.added`, `player.removed`, `player.updated`, `seat.changed`. Future events from other modules are not yet implemented.

Legacy `/ws` messages and REST routes are retained so OBS can keep using v0.2 URLs. `client=overlay` flags a connection for installation interlock; do not remove it. Future contracts must be introduced with compatible versions.

## Dependencies and contracts

`module.json` has `requires` and `provides` capabilities. `hj.effects` needs `players.api` and accesses it **only via** `ctx.get_service('players.api')`; `hj.players` registers `get_player(player_id)`, `get_active_players()` and `theme_exists(theme_id)`.

SemVer `MAJOR.MINOR.PATCH`; `host_api` accepts `1.x` or exact `1.0.0`. Breaking changes require new CORE API with a coordinated upgrade. Other modules must never import a sibling module's backend, CSS or internal files.

## User data and migrations

`%LOCALAPPDATA%\HiJackLive\production` and `...\staging` are separate host data roots. Module code is in `modules/`; namespaced storage is in `module_data/hj.<name>.sqlite3`. Legacy seating/settings remain in `hi-jack.sqlite3` snapshot schema v2 to preserve the 0.2 release.

An optional manifest `data_schema` (0 if unused) refers to numbered `migrations/0001_*.py`, each exporting `upgrade(storage)` with `ctx.storage()`-compatible `get/set/delete`. Before migration, CORE creates a SQLite file backup. Migration failures restore the file and prevent activation; startup module failure after update can trigger module-code rollback. A future change to the **legacy global state schema** requires a coordinated CORE upgrade and dedicated migration.

## Installation protocol

POST `application/zip` to `/api/modules/validate`, inspect version/changes, then POST to `/api/modules/install`. The ZIP contains exactly one top-level `hj_players/`-style folder, and complete SHA256 `checksums.json`. CORE checks path traversal, symlinks, duplicate paths, size limits, module structure, API compatibility and plugin `self_check`. It stages it, copies the previous module to `%LOCALAPPDATA%\HiJackLive\<profile>\module_backups`, atomically swaps when possible, and returns `restart_required`.

No installation or rollback while OBS overlay WebSockets are connected. `POST /api/modules/hj.players/rollback` restores previous code. Rolling back **module data schemas** to an older incompatible format is not supported; the manager rejects older incompatible schema versions at startup.

## Architecture boundaries / not-yet-implemented

`hj_obs_control`, `hj_vision`, `hj_player_memory`, `hj_ai_commentator`, `hj_highlights`, `hj_auto_recap` are disabled placeholders; no working feature should be implied. Real Windows EXE, OBS scene activation, camera preview capture and production stream testing are pending.
