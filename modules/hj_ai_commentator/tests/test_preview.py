"""Tests for no-broadcast, confirmation-gated offline preview."""
import pytest
from modules.hj_ai_commentator.backend.preview import build_preview

def test_confirmed_preview_is_explicitly_not_for_broadcast():
    result = build_preview("player.added", {"nickname": "Jack"}, True)
    assert "Jack" in result["text"]
    assert result["mode"] == "offline_template"
    assert result["approved_for_broadcast"] is False
    assert result["audio_generated"] is False

@pytest.mark.parametrize("confirmed", [False, None, 0])
def test_unconfirmed_event_is_rejected(confirmed):
    with pytest.raises(ValueError, match="confirmed"):
        build_preview("player.added", {"nickname": "Jack"}, confirmed)

def test_unknown_event_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        build_preview("winner.declared", {}, True)

def test_invalid_player_name_falls_back():
    result = build_preview("player.added", {"nickname": "x" * 100}, True)
    assert "игрок" in result["text"]
