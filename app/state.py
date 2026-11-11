"""SQLite-backed snapshots and validated state transitions for Hi, Jack Live Overlays."""
from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
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


def ensure_placements(state: dict, player: dict) -> None:
    for key, profile in state["profiles"].items():
        profile["placements"].setdefault(player["id"], default_placement(player["seat"], key, player.get("is_dealer", False)))
    for key, layout in state["drafts"].items():
        layout.setdefault(player["id"], copy.deepcopy(state["profiles"][key]["placements"][player["id"]]))


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


def validate_import(data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError("JSON должен содержать объект конфигурации")
    required = {"players", "dealer", "profiles", "settings", "active_profile"}
    if not required.issubset(data):
        raise ValueError("В конфигурации отсутствуют обязательные поля")
    cleaned = initial_state()
    players = data["players"]
    if not isinstance(players, list) or len(players) > 10:
        raise ValueError("Допускается максимум 10 игроков")
    seen_ids, seen_seats = set(), set()
    for p in players:
        if not isinstance(p, dict): raise ValueError("Некорректный игрок")
        nickname = clean_nickname(p.get("nickname"))
        pid = str(p.get("id", ""))
        if not pid or pid in seen_ids or pid == "dealer" or len(pid) > 64: raise ValueError("Неверный ID игрока")
        seen_ids.add(pid)
        seat = clean_seat(p.get("seat"), cleaned["players"])
        if seat: seen_seats.add(seat)
        status = p.get("status", "active")
        style = p.get("style", "classic")
        if status not in ALLOWED_STATUSES or (style is not None and style not in ALLOWED_STYLES): raise ValueError("Неверный стиль или статус")
        theme = p.get("theme")
        if theme is not None and (not isinstance(theme,str) or not THEME_ID_RE.fullmatch(theme)):
            raise ValueError("Неверный идентификатор темы игрока")
        cleaned["players"].append({"id":pid, "nickname":nickname,"seat":seat, "status":status,
                                   "style":style,"theme":theme,"visible":bool(p.get("visible",True)),"is_dealer":False})
    d = data["dealer"]
    if not isinstance(d,dict): raise ValueError("Некорректные данные дилера")
    d_theme = d.get("theme")
    if d_theme is not None and (not isinstance(d_theme,str) or not THEME_ID_RE.fullmatch(d_theme)):
        raise ValueError("Неверная тема дилера")
    cleaned["dealer"].update({"nickname":clean_nickname(d.get("nickname","ДИЛЕР")),"visible":bool(d.get("visible",False)), "theme":d_theme})
    profiles = data["profiles"]
    if not isinstance(profiles,dict) or not 1<=len(profiles)<=30: raise ValueError("Некорректные профили")
    cleaned["profiles"] = {}
    legal_ids = seen_ids | {"dealer"}
    for key, prof in profiles.items():
        if not isinstance(key,str) or not key.isascii() or not key.replace("-","").replace("_","").isalnum() or len(key)>32 or not isinstance(prof,dict):
            raise ValueError("Некорректный ID профиля")
        name = str(prof.get("name",key))[:40]
        placements = prof.get("placements",{})
        if not isinstance(placements,dict): raise ValueError("Некорректная раскладка")
        cleaned["profiles"][key] = {"name":name,"placements":{pid:clean_placement(v) for pid,v in placements.items() if pid in legal_ids}}
    for p in cleaned["players"]+[cleaned["dealer"]]: ensure_placements(cleaned,p)
    active = data["active_profile"]
    cleaned["active_profile"] = active if active in cleaned["profiles"] else next(iter(cleaned["profiles"]))
    settings = data.get("settings",{})
    if isinstance(settings,dict):
        try: cleaned["settings"]["volume"] = max(0,min(1,float(settings.get("volume",.28))))
        except (ValueError,TypeError): pass
        theme = settings.get("theme",DEFAULT_THEME)
        style = settings.get("default_style","classic")
        if not isinstance(theme,str) or not THEME_ID_RE.fullmatch(theme): raise ValueError("Неверная общая тема")
        if style not in ALLOWED_STYLES: raise ValueError("Неверный общий стиль")
        cleaned["settings"].update({"theme":theme,"default_style":style})
    return cleaned


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS snapshots (name TEXT PRIMARY KEY, content TEXT NOT NULL, updated_at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS undo_history (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, created_at TEXT NOT NULL)")
            row = conn.execute("SELECT content FROM snapshots WHERE name='current'").fetchone()
            self.state = json.loads(row[0]) if row else initial_state()
            old_schema = bool(row) and (self.state.get("schema_version",0) < 2 or
                "theme" not in self.state.get("settings",{}) or any(
                "height" not in p for prof in self.state.get("profiles",{}).values()
                for p in prof.get("placements",{}).values()))
            if old_schema:
                folder = self.path.parent / "backups"
                folder.mkdir(exist_ok=True)
                with sqlite3.connect(folder / f"before-v2-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite3") as dest:
                    conn.backup(dest)
            # Migrate existing 0.1 SQLite snapshots non-destructively.
            self.state.setdefault("settings",{}).setdefault("theme",DEFAULT_THEME)
            self.state["settings"].setdefault("default_style","classic")
            for player in self.state["players"] + [self.state["dealer"]]:
                player.setdefault("theme",None)
                ensure_placements(self.state, player)
            for profile in self.state["profiles"].values():
                for pid,placement in list(profile["placements"].items()):
                    profile["placements"][pid] = clean_placement(placement)
            for draft in self.state.get("drafts",{}).values():
                for pid,placement in list(draft.items()):
                    draft[pid] = clean_placement(placement)
            self.state["schema_version"] = 2
            if not row or old_schema: self._write(conn)
        # Corrupt drafts should never supersede published layout after app reboot.

    def db(self):
        return sqlite3.connect(self.path, timeout=10)

    def _write(self, conn):
        conn.execute("INSERT OR REPLACE INTO snapshots VALUES ('current',?,?)",(json.dumps(self.state,ensure_ascii=False),now()))

    def commit(self, next_state: dict) -> dict:
        previous = copy.deepcopy(self.state)
        next_state["revision"] = previous["revision"]+1
        with self.db() as conn:
            conn.execute("INSERT INTO undo_history (content,created_at) VALUES (?,?)",(json.dumps(previous,ensure_ascii=False),now()))
            conn.execute("DELETE FROM undo_history WHERE id NOT IN (SELECT id FROM undo_history ORDER BY id DESC LIMIT 40)")
            self.state = next_state
            self._write(conn)
        return copy.deepcopy(self.state)

    def undo(self) -> dict:
        with self.db() as conn:
            row = conn.execute("SELECT id,content FROM undo_history ORDER BY id DESC LIMIT 1").fetchone()
            if row is None: raise ValueError("История изменений пуста")
            restored = json.loads(row[1])
            restored["revision"] = self.state["revision"]+1
            conn.execute("DELETE FROM undo_history WHERE id=?",(row[0],))
            self.state = restored
            self._write(conn)
        return copy.deepcopy(self.state)

    def backup(self) -> Path:
        folder = self.path.parent / "backups"
        folder.mkdir(exist_ok=True)
        output = folder / f"hi-jack-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite3"
        with self.db() as conn, sqlite3.connect(output) as dest:
            conn.backup(dest)
        return output
