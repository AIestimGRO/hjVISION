"""Safe offline commentary preview. No LLM calls, voice output or OBS effects."""
from __future__ import annotations

SUPPORTED_EVENTS = {
    "player.added": "К столу присоединяется {player}.",
    "player.removed": "{player} покидает стол.",
    "player.updated": "Обновилась информация об игроке {player}.",
    "seat.changed": "Изменилась рассадка за столом.",
}
MAX_NAME = 64

def build_preview(event_type: str, payload: dict, confirmed: bool) -> dict:
    """Return a clearly labelled *template*, never a purported AI-generated claim."""
    if not confirmed:
        raise ValueError("Only operator-confirmed events can be previewed")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if event_type not in SUPPORTED_EVENTS:
        raise ValueError("Unsupported event type")
    player = payload.get("player_name") or payload.get("nickname") or "игрок"
    if not isinstance(player, str) or not player.strip() or len(player) > MAX_NAME:
        player = "игрок"
    player = " ".join(player.split()).replace("{", "").replace("}", "")
    return {
        "mode": "offline_template",
        "event_type": event_type,
        "text": SUPPORTED_EVENTS[event_type].format(player=player),
        "approved_for_broadcast": False,
        "audio_generated": False,
    }
