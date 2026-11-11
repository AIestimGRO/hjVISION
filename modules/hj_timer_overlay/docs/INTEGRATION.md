# Integration
Installs independently into HI, JACK LIVE CORE API 1.x; uses core.storage service, ui.register and dedicated routes. Requires no changes to HJ Players, OBS Control, HJ Effects or remote timer deployment.
Source: AIestimGRO/hi-jack-timer app/server.py GET /api/state; app/timer_state.py TimerState.to_dict. Timer server remains authoritative for status and remaining_sec. No remote write calls.
OBS: add a separate Browser Source, 1920x1080, to the scene. In editor pick matching camera profile and publish. Use OBS fit to screen. Install while OBS overlay clients disconnected.
