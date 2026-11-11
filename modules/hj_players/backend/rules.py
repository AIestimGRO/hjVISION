"""Independent player domain rules. Frozen public state-v2 contract lives in CORE.
Changes to persisted placement schema require a compatible host API migration.
"""
from __future__ import annotations
import copy
import re
from datetime import datetime,timezone
from uuid import uuid4

ALLOWED_STYLES = {"compact", "classic", "premium"}
ALLOWED_STATUSES = {"active", "all-in", "fold", "out", "winner"}
THEME_ID_RE = __import__("re").compile(r"^[a-z][a-z0-9-]{0,47}$")
DEFAULT_THEME = "bronze-premium"
EFFECTS = ["ALL-IN", "PLAYER OUT", "DOUBLE UP", "WINNER", "FINAL TABLE", "BREAK", "BOUNTY", "JACKPOT"]


def initial_state() -> dict:
    return {
        "schema_version": 2,
        "revision": 0,
        "players": [],
        "dealer": {"id": "dealer", "nickname": "ДИЛЕР", "seat": None, "visible": False,
                   "status": "active", "style": "compact", "theme": None, "is_dealer": True},
        "profiles": {
            "top": {"name": "TOP VIEW", "placements": {}},
            "front": {"name": "FRONT VIEW", "placements": {}},
            "side": {"name": "SIDE VIEW", "placements": {}},
            "final": {"name": "FINAL TABLE", "placements": {}},
        },
        "drafts": {},
        "active_profile": "top",
        "scene_mappings": {},
        "settings": {"volume": .28, "effects_enabled": True, "theme": DEFAULT_THEME, "default_style": "classic"},
        "effect_catalog": [{"id": n.lower().replace(' ', '-'), "label": n, "duration": 3100, "enabled": True, "sound": True}
                           for n in EFFECTS],
    }


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_placement(seat: int | None, profile: str, dealer: bool = False) -> dict:
    if dealer:
        x, y = .095, .33
    elif profile == "top" or profile == "final":
        slots = [(0.18,.09),(.39,.09),(.60,.09),(.81,.09),(.89,.31),
                 (.89,.70),(.72,.91),(.51,.91),(.30,.91),(.11,.70)]
        x,y = slots[(seat - 1) % 10] if seat else (.5,.5)
    elif profile == "side":
        slots = [(0.15,.18),(.38,.18),(.62,.18),(.85,.18),(.86,.50),
                 (.86,.82),(.63,.82),(.38,.82),(.15,.82),(.14,.50)]
        x,y = slots[(seat - 1) % 10] if seat else (.5,.5)
    else:
        slots = [(0.18,.20),(.39,.20),(.60,.20),(.81,.20),(.87,.52),
                 (.81,.83),(.60,.83),(.39,.83),(.18,.83),(.13,.52)]
        x,y = slots[(seat - 1) % 10] if seat else (.5,.5)
    return {"x":x, "y":y, "width":.15, "height":.065, "scale":1, "font_size":24, "padding":8, "glow":.6, "rotation":0, "opacity":1, "visible":True, "style":None}


BADGE_PRESET_KEYS = ("width", "height", "scale", "font_size", "padding", "glow", "rotation", "opacity", "style")


def badge_visual_settings(placement: dict) -> dict:
    """Only appearance is reusable; never use seat coordinates or visibility as defaults."""
    clean = clean_placement({**default_placement(None, "top"), **placement})
    return {key: clean[key] for key in BADGE_PRESET_KEYS}


def configured_default_placement(state: dict, seat: int | None, profile: str, dealer: bool = False) -> dict:
    base = default_placement(seat, profile, dealer)
    if dealer:
        return base
    saved = state.get("settings", {}).get("badge_default")
    if not isinstance(saved, dict):
        return base
    return {**base, **badge_visual_settings(saved)}


def ensure_placements(state: dict, player: dict) -> None:
    for key, profile in state["profiles"].items():
        profile["placements"].setdefault(player["id"], configured_default_placement(state, player["seat"], key, player.get("is_dealer", False)))
    for key, layout in state["drafts"].items():
        layout.setdefault(player["id"], copy.deepcopy(state["profiles"][key]["placements"][player["id"]]))


def reposition_on_first_seat(state: dict, player: dict, old_seat: int | None) -> None:
    """Place an initially unseated player in their first physical box.

    Never overwrite manually moved badges: only untouched (centered) positions
    are adjusted. Subsequent seat changes preserve on-air/editor coordinates.
    Each camera profile gets its own standard coordinates.
    """
    seat = player.get("seat")
    if old_seat is not None or seat is None or player.get("is_dealer"):
        return
    for profile_id, profile in state["profiles"].items():
        target = default_placement(seat, profile_id)
        live = profile["placements"].get(player["id"])
        if live is not None and live.get("x") == .5 and live.get("y") == .5:
            live["x"], live["y"] = target["x"], target["y"]
        draft = state["drafts"].get(profile_id, {}).get(player["id"])
        if draft is not None and draft.get("x") == .5 and draft.get("y") == .5:
            draft["x"], draft["y"] = target["x"], target["y"]


def clean_nickname(name: object) -> str:
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 36:
        raise ValueError("Никнейм должен содержать 1–36 символов")
    return name.strip()


def clean_seat(seat: object, players: list, exclude_id: str | None = None) -> int | None:
    if seat is None or seat == "":
        return None
    if isinstance(seat, bool) or not isinstance(seat, int) or not 1 <= seat <= 10:
        raise ValueError("Бокс должен быть числом от 1 до 10")
    if any(p["seat"] == seat and p["id"] != exclude_id for p in players):
        raise ValueError(f"Бокс № {seat} уже занят")
    return seat


def clean_placement(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Неверные параметры расположения")
    def num(key, minimum, maximum, default):
        v = raw.get(key, default)
        if isinstance(v, bool) or not isinstance(v, (float, int)) or not minimum <= v <= maximum:
            raise ValueError(f"Некорректное значение {key}")
        return round(float(v), 5)
    if not isinstance(raw.get("visible", True), bool):
        raise ValueError("visible должен быть логическим значением")
    style = raw.get("style")
    if style is not None and style not in ALLOWED_STYLES:
        raise ValueError("Неверный стиль для профиля камеры")
    return {"x": num("x",0,1,.5), "y": num("y",0,1,.5),
            "width": num("width",.04,.75,.15), "height":num("height",.02,.4,.065),
            "scale":num("scale",.25,3,1), "font_size":num("font_size",8,88,24),
            "padding":num("padding",0,40,8),"glow":num("glow",0,1,.6),
            "rotation": num("rotation",-180,180,0),
            "opacity":num("opacity",.1,1,1), "visible":raw.get("visible",True), "style":style}

