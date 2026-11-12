# JACK AI Commentator

Development module, version **0.1.0**: offline template preview prototype,
NOT a working AI voice commentator. Disabled by default in `module.json`.

The admin-only preview endpoint accepts operator-confirmed sample events,
creates safe sample text and explicitly marks the result non-broadcastable.
No OpenAI API, TTS, OBS output, GitHub rule sync or live inference yet.

Code belongs in `modules/hj_ai_commentator/`; approved character/rules
belong in independent `hi-jack-ai-training` releases reviewed by the trainers.
Never commit API keys, club histories or local user settings.

Test: `python -m pytest -q modules/hj_ai_commentator/tests`.
Do not deploy on-air or merge into main without Windows/OBS acceptance.

Next: local secret storage, OpenAI adapter in preview-only mode, controlled
audio output, independent training sync/rollback, provenance and integration tests.
