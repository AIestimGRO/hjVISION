# JACK AI Commentator — API v0.1.0 (development)

Module is **disabled by default**. This is an offline, deterministic template preview,
NOT OpenAI-generated commentary. No audio and no OBS output.

When enabled in a development build:
- `GET /api/jack-ai/status` — admin-authorized capability flags.
- `POST /api/jack-ai/preview` — admin-authorized JSON:
  `{"event_type":"player.added","payload":{"nickname":"Jack"},"confirmed":true}`.
  Returns `mode=offline_template`, `approved_for_broadcast=false`,
  `audio_generated=false`; unknown or unconfirmed events return HTTP 422.

No player state changes. Training rule releases use a separate repository.
