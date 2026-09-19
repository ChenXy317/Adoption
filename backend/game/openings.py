"""
开场阶段 — 新建存档时的可选起点（时间、属性、记忆与 system 开局说明）。
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import CALENDAR_DEFAULT, SEEDS_DIR
from game import clock, events, memory, scenes
from game.attributes import clamp, phase_of
from helpers import load_attr_values
from orm import AttributeDef, Memory, Message, Save, SceneDef

logger = logging.getLogger(__name__)

DEFAULT_KEY = "rain_night"
OPENING_AT_FLAG = "opening_at"
_SYSTEM_MAX = 8000
_TEXT_MAX = 4000
_NARRATION_MAX = 2000

_cache: list[dict] | None = None


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_all() -> list[dict]:
    """读取种子开场列表（按 sort、key 排序）。"""
    global _cache
    if _cache is not None:
        return _cache
    path = SEEDS_DIR / "openings.json"
    items: list[dict] = []
    if not path.exists():
        logger.warning("未找到开场种子文件: %s", path)
        _cache = items
        return items
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        name = str(item.get("name") or "").strip()
        if not key or not name:
            continue
        items.append(item)
    items.sort(key=lambda row: (_int(row.get("sort"), 0), str(row.get("key") or "")))
    _cache = items
    return items


def get(key: str | None) -> dict | None:
    """按 key 取开场；空 key 回落到默认项。"""
    wanted = str(key or "").strip() or DEFAULT_KEY
    for item in load_all():
        if str(item.get("key") or "") == wanted:
            return item
    return None


def _time_label(item: dict) -> str:
    calendar = item.get("calendar") if isinstance(item.get("calendar"), dict) else {}
    settings = {
        "calendar": {
            "month": _int(calendar.get("month"), CALENDAR_DEFAULT["month"]),
            "day": _int(calendar.get("day"), CALENDAR_DEFAULT["day"]),
            "hour": _int(calendar.get("hour"), CALENDAR_DEFAULT["hour"]),
            "minute": _int(calendar.get("minute"), CALENDAR_DEFAULT["minute"]),
        }
    }
    minutes = max(0, _int(item.get("game_minutes"), 0))
    return clock.full_label(clock.absolute_minutes(minutes, settings))


def _attrs_map(item: dict) -> dict[str, float]:
    raw = item.get("attrs") if isinstance(item.get("attrs"), dict) else {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def public_list() -> list[dict]:
    """供前端选择的开场摘要（不含 system 原文）。"""
    items = []
    for item in load_all():
        attrs = _attrs_map(item)
        items.append({
            "key": str(item.get("key") or ""),
            "name": str(item.get("name") or ""),
            "blurb": str(item.get("blurb") or "").strip(),
            "time_label": _time_label(item),
            "phase": phase_of(attrs),
        })
    return items


def snapshot(item: dict) -> dict:
    """写入存档 settings.opening 的开局说明（对话组装会读这里）。"""
    overlay_in = item.get("persona_overlay")
    overlay: dict[str, str] = {}
    if isinstance(overlay_in, dict):
        for key, value in list(overlay_in.items())[:16]:
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text:
                continue
            overlay[str(key)[:64]] = text[:_TEXT_MAX]
    return {
        "key": str(item.get("key") or "")[:64],
        "name": str(item.get("name") or "")[:64],
        "system": str(item.get("system") or "").strip()[:_SYSTEM_MAX],
        "persona_overlay": overlay,
    }


def calendar_of(item: dict) -> dict:
    raw = item.get("calendar") if isinstance(item.get("calendar"), dict) else {}
    out = dict(CALENDAR_DEFAULT)
    for key in out:
        if key in raw:
            out[key] = _int(raw.get(key), out[key])
    return out


def apply(session: Session, save: Save, item: dict) -> None:
    """把开场落到存档：属性、标记、记忆、旁白，并进入对应开场场景。"""
    defs = list(session.scalars(select(AttributeDef)))
    defs_map = {row.key: row for row in defs}
    values = load_attr_values(session, save.id)
    abs_now = clock.absolute_minutes(save.game_minutes, save.settings or {})

    flags = item.get("flags") if isinstance(item.get("flags"), dict) else {}
    for key, value in flags.items():
        name = str(key).strip()[:64]
        if not name:
            continue
        events.set_flag(session, save.id, name, value)

    events.set_flag(session, save.id, OPENING_AT_FLAG, abs_now)

    mood = str(item.get("mood_label") or "").strip()[:32]
    if mood:
        events.set_mood_label(session, save.id, mood, abs_now)

    for entry in item.get("memories") or []:
        if not isinstance(entry, dict):
            continue
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        kind = str(entry.get("kind") or "event").strip()
        if kind not in memory.KINDS:
            kind = "event"
        importance = max(1, min(10, _int(entry.get("importance"), 7)))
        session.add(
            Memory(
                save_id=save.id,
                kind=kind,
                content=content[:2000],
                importance=importance,
            )
        )

    narration = str(item.get("narration") or "").strip()
    if narration:
        session.add(
            Message(
                save_id=save.id,
                role="event",
                content=narration[:_NARRATION_MAX],
                meta={
                    "kind": "opening",
                    "opening_key": str(item.get("key") or ""),
                    "opening_name": str(item.get("name") or ""),
                },
                game_minutes_at=abs_now,
            )
        )

    scene_key = str(item.get("scene_key") or "").strip()
    if not scene_key:
        return
    scene = session.scalar(select(SceneDef).where(SceneDef.key == scene_key))
    if scene is None:
        logger.warning("开场场景不存在，已跳过进入: %s", scene_key)
        return
    ctx = events.build_context(session, save, values)
    scenes.enter_scene(
        session, save, scene, ctx, values, defs_map, source="opening"
    )
