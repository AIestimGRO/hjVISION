# Architecture
Timer remote API -> server-side threaded urllib poll / 1.5s cache / 2.5s network timeout -> local FastAPI GET /api/hj-timer/state -> browser rendering via 220ms local tick -> transparent OBS.
Timer layout storage is namespaced SQLite, with draft/published per profile. It cannot modify player positions or remote timer.
