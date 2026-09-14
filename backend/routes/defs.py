"""
定义管理 — 属性 / 事件 / 场景定义 CRUD（PLAN 5.2 / 5.3）。

所有 key 创建后不可改（避免引用孤儿），仅支持启停与字段调整；
事件/场景定义标出内置（种子）来源，内置定义重启时会被种子恢复字段。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from config import SEEDS_DIR
from db import get_session
from game.attributes import clamp
from helpers import error
from orm import AttributeDef, AttributeValue, EventDef, SceneDef
from schemas import (
    AttributeDefIn,
    AttributeDefPatch,
    EventDefIn,
    EventDefPatch,
    SceneDefIn,
    SceneDefPatch,
)

router = APIRouter(tags=["defs"])

EVENT_CATEGORIES = ("random", "fixed", "manual", "work")


def _def_dict(d: AttributeDef) -> dict:
    return {
        "id": d.id,
        "key": d.key,
        "name": d.name,
        "category": d.category,
        "min": d.min,
        "max": d.max,
        "default_value": d.default_value,
        "tick_rule": d.tick_rule,
        "ai_editable": bool(d.ai_editable),
        "sort": d.sort,
        "enabled": bool(d.enabled),
    }


@router.get("/api/attribute-defs")
def list_attribute_defs(session: Session = Depends(get_session)):
    defs = session.scalars(
        select(AttributeDef).order_by(AttributeDef.sort, AttributeDef.id)
    ).all()
    return [_def_dict(d) for d in defs]


@router.post("/api/attribute-defs")
def create_attribute_def(
    req: AttributeDefIn, session: Session = Depends(get_session)
):
    exists = session.scalar(
        select(AttributeDef).where(AttributeDef.key == req.key)
    )
    if exists:
        error("duplicate_key", f"属性 key「{req.key}」已存在", 409)
    if req.min >= req.max:
        error("invalid_range", "最小值必须小于最大值", 400)
    definition = AttributeDef(
        key=req.key,
        name=req.name.strip(),
        category=req.category.strip() or "stat",
        min=req.min,
        max=req.max,
        default_value=clamp(req.default_value, req.min, req.max),
        tick_rule=req.tick_rule,
        ai_editable=req.ai_editable,
        sort=req.sort,
        enabled=req.enabled,
    )
    session.add(definition)
    session.commit()
    return _def_dict(definition)


@router.patch("/api/attribute-defs/{def_id}")
def update_attribute_def(
    def_id: int, req: AttributeDefPatch, session: Session = Depends(get_session)
):
    definition = session.get(AttributeDef, def_id)
    if definition is None:
        error("def_not_found", "属性不存在", 404)
    if req.name is not None:
        definition.name = req.name.strip()
    if req.category is not None:
        definition.category = req.category.strip() or "stat"
    if req.min is not None:
        definition.min = req.min
    if req.max is not None:
        definition.max = req.max
    if definition.min >= definition.max:
        error("invalid_range", "最小值必须小于最大值", 400)
    if req.default_value is not None:
        definition.default_value = req.default_value
    definition.default_value = clamp(
        definition.default_value, definition.min, definition.max
    )
    if "tick_rule" in req.model_fields_set:
        definition.tick_rule = req.tick_rule
    if req.ai_editable is not None:
        definition.ai_editable = req.ai_editable
    if req.sort is not None:
        definition.sort = req.sort
    if req.enabled is not None:
        definition.enabled = req.enabled
    for value_row in session.scalars(
        select(AttributeValue).where(AttributeValue.attr_key == definition.key)
    ):
        value_row.value = clamp(value_row.value, definition.min, definition.max)
    session.commit()
    return _def_dict(definition)


@router.delete("/api/attribute-defs/{def_id}")
def delete_attribute_def(
    def_id: int, session: Session = Depends(get_session)
):
    definition = session.get(AttributeDef, def_id)
    if definition is None:
        error("def_not_found", "属性不存在", 404)
    session.execute(
        delete(AttributeValue).where(AttributeValue.attr_key == definition.key)
    )
    session.execute(delete(AttributeDef).where(AttributeDef.id == def_id))
    session.commit()
    return {"ok": True}


# ── 事件定义 ──

_seed_keys_cache: dict[str, tuple[float, set[str]]] = {}


def _seed_keys(filename: str) -> set[str]:
    """读取种子文件中定义的 key 集合（按 mtime 缓存，供内置定义标记复用）。"""
    path = SEEDS_DIR / filename
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return set()
    cached = _seed_keys_cache.get(filename)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()
    keys = {
        str(item.get("key") or "").strip()
        for item in items
        if isinstance(item, dict) and str(item.get("key") or "").strip()
    }
    _seed_keys_cache[filename] = (mtime, keys)
    return keys


def _event_dict(d: EventDef, seed_keys: set[str]) -> dict:
    return {
        "id": d.id,
        "key": d.key,
        "name": d.name,
        "category": d.category,
        "trigger": d.trigger or {},
        "cost": d.cost or {},
        "effects": d.effects or {},
        "prompt_template": d.prompt_template or "",
        "once": bool(d.once),
        "cooldown_minutes": int(d.cooldown_minutes or 0),
        "priority": int(d.priority or 0),
        "enabled": bool(d.enabled),
        "from_seed": d.key in seed_keys,
    }


def _scene_dict(d: SceneDef, seed_keys: set[str]) -> dict:
    return {
        "id": d.id,
        "key": d.key,
        "name": d.name,
        "category": d.category,
        "enter_trigger": d.enter_trigger or {},
        "enter_cost": d.enter_cost or {},
        "scene_prompt": d.scene_prompt or "",
        "goal": d.goal or "",
        "min_turns": int(d.min_turns or 0),
        "max_turns": int(d.max_turns or 0),
        "exit": d.exit or {},
        "effects": d.effects or {},
        "next_scenes": list(d.next_scenes or []),
        "once": bool(d.once),
        "cooldown_minutes": int(d.cooldown_minutes or 0),
        "priority": int(d.priority or 0),
        "enabled": bool(d.enabled),
        "from_seed": d.key in seed_keys,
    }


def _clean_scene_keys(values) -> list[str]:
    return [str(x).strip()[:64] for x in (values or []) if str(x).strip()]


@router.get("/api/event-defs")
def list_event_defs(session: Session = Depends(get_session)):
    seed_keys = _seed_keys("events.json")
    rows = session.scalars(
        select(EventDef).order_by(EventDef.priority.desc(), EventDef.id)
    ).all()
    return [_event_dict(row, seed_keys) for row in rows]


@router.post("/api/event-defs")
def create_event_def(req: EventDefIn, session: Session = Depends(get_session)):
    if req.category not in EVENT_CATEGORIES:
        error("invalid_category", "事件分类只能是 random / fixed / manual / work", 400)
    if session.scalar(select(EventDef).where(EventDef.key == req.key)):
        error("duplicate_key", f"事件 key「{req.key}」已存在", 409)
    definition = EventDef(**req.model_dump())
    session.add(definition)
    session.commit()
    return _event_dict(definition, _seed_keys("events.json"))


@router.patch("/api/event-defs/{def_id}")
def update_event_def(
    def_id: int, req: EventDefPatch, session: Session = Depends(get_session)
):
    definition = session.get(EventDef, def_id)
    if definition is None:
        error("def_not_found", "事件不存在", 404)
    fields = req.model_dump(exclude_unset=True)
    if fields.get("category") is not None and fields["category"] not in EVENT_CATEGORIES:
        error("invalid_category", "事件分类只能是 random / fixed / manual / work", 400)
    for name, value in fields.items():
        if value is None:
            continue
        setattr(definition, name, value)
    session.commit()
    return _event_dict(definition, _seed_keys("events.json"))


@router.delete("/api/event-defs/{def_id}")
def delete_event_def(def_id: int, session: Session = Depends(get_session)):
    definition = session.get(EventDef, def_id)
    if definition is None:
        error("def_not_found", "事件不存在", 404)
    session.execute(delete(EventDef).where(EventDef.id == def_id))
    session.commit()
    return {"ok": True}


# ── 场景定义 ──

@router.get("/api/scene-defs")
def list_scene_defs(session: Session = Depends(get_session)):
    seed_keys = _seed_keys("scenes.json")
    rows = session.scalars(
        select(SceneDef).order_by(SceneDef.priority.desc(), SceneDef.id)
    ).all()
    return [_scene_dict(row, seed_keys) for row in rows]


@router.post("/api/scene-defs")
def create_scene_def(req: SceneDefIn, session: Session = Depends(get_session)):
    if req.max_turns > 0 and req.min_turns > req.max_turns:
        error("invalid_turns", "min_turns 不能大于 max_turns", 400)
    if session.scalar(select(SceneDef).where(SceneDef.key == req.key)):
        error("duplicate_key", f"场景 key「{req.key}」已存在", 409)
    payload = req.model_dump()
    payload["next_scenes"] = _clean_scene_keys(payload.get("next_scenes"))
    definition = SceneDef(**payload)
    session.add(definition)
    session.commit()
    return _scene_dict(definition, _seed_keys("scenes.json"))


@router.patch("/api/scene-defs/{def_id}")
def update_scene_def(
    def_id: int, req: SceneDefPatch, session: Session = Depends(get_session)
):
    definition = session.get(SceneDef, def_id)
    if definition is None:
        error("def_not_found", "场景不存在", 404)
    fields = req.model_dump(exclude_unset=True)
    min_turns = (
        definition.min_turns
        if fields.get("min_turns") is None
        else fields["min_turns"]
    )
    max_turns = (
        definition.max_turns
        if fields.get("max_turns") is None
        else fields["max_turns"]
    )
    if max_turns > 0 and min_turns > max_turns:
        error("invalid_turns", "min_turns 不能大于 max_turns", 400)
    for name, value in fields.items():
        if value is None:
            continue
        if name == "next_scenes":
            value = _clean_scene_keys(value)
        setattr(definition, name, value)
    session.commit()
    return _scene_dict(definition, _seed_keys("scenes.json"))


@router.delete("/api/scene-defs/{def_id}")
def delete_scene_def(def_id: int, session: Session = Depends(get_session)):
    definition = session.get(SceneDef, def_id)
    if definition is None:
        error("def_not_found", "场景不存在", 404)
    session.execute(delete(SceneDef).where(SceneDef.id == def_id))
    session.commit()
    return {"ok": True}
