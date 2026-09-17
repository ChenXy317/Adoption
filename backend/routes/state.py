"""
存档状态与消息历史 — 前端主界面数据来源（PLAN 第 7 节）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_session
from game import clock, events, scenes
from game.attributes import phase_of, tendency_of
from helpers import (
    attribute_items,
    behavior_count,
    character_dict,
    get_save_character,
    get_save_or_error,
    load_attr_values,
)
from orm import AttributeDef, EventDef, EventLog, Message

router = APIRouter(tags=["state"])

MESSAGES_MAX_LIMIT = 200
WALLET_FLOW_LIMIT = 8
WALLET_FLOW_SCAN = 120


def _wallet_flows(session: Session, save_id: int) -> list[dict]:
    """最近金钱收支（来源为 event_logs 的效果与扣除明细）。"""
    rows = list(
        session.scalars(
            select(EventLog)
            .where(EventLog.save_id == save_id)
            .order_by(EventLog.id.desc())
            .limit(WALLET_FLOW_SCAN)
        )
    )
    flows: list[dict] = []
    for log in rows:
        meta = log.meta or {}
        amount = 0.0
        for change in meta.get("attrs") or []:
            if change.get("key") == "money":
                amount += float(change.get("delta") or 0)
        for change in meta.get("cost_attrs") or []:
            if change.get("key") == "money":
                amount += float(change.get("delta") or 0)
        if amount == 0:
            continue
        abs_at = int(log.game_minutes_at or 0)
        flows.append({
            "id": log.id,
            "name": meta.get("name") or meta.get("key") or "事件",
            "category": meta.get("category", ""),
            "amount": round(amount, 2),
            "game_minutes_at": abs_at,
            "virtual_label": clock.time_label(abs_at),
        })
        if len(flows) >= WALLET_FLOW_LIMIT:
            break
    return flows


@router.get("/api/saves/{save_id}/state")
def get_state(save_id: int, session: Session = Depends(get_session)):
    save = get_save_or_error(session, save_id)
    settings = save.settings or {}
    absolute = clock.absolute_minutes(save.game_minutes, settings)
    split = clock.split(absolute)
    defs = session.scalars(
        select(AttributeDef).order_by(AttributeDef.sort, AttributeDef.id)
    ).all()
    values = load_attr_values(session, save_id)
    character = get_save_character(session, save)
    active_flag = scenes.get_active(session, save_id)
    recent_rows = session.execute(
        select(EventLog, EventDef.name)
        .outerjoin(EventDef, EventLog.event_id == EventDef.id)
        .where(EventLog.save_id == save_id)
        .order_by(EventLog.id.desc())
        .limit(5)
    ).all()
    recent_events = []
    for log, def_name in reversed(recent_rows):
        meta = log.meta or {}
        abs_at = int(log.game_minutes_at or 0)
        recent_events.append({
            "id": log.id,
            "event_key": meta.get("key", ""),
            "name": meta.get("name") or def_name or "事件",
            "category": meta.get("category", ""),
            "content": log.content,
            "game_minutes_at": abs_at,
            "virtual_label": clock.time_label(abs_at),
        })
    action_items = events.manual_candidates(session, save, values)
    flags = events.load_flags(session, save_id)
    attrs = attribute_items(defs, values)
    money = next(
        (item["value"] for item in attrs if item["key"] == "money"),
        values.get("money", 0.0),
    )
    return {
        "save": {
            "id": save.id,
            "name": save.name,
            "status": save.status,
            "model_key": save.model_key,
            "game_minutes": save.game_minutes,
        },
        "character": character_dict(character),
        "phase": phase_of(values),
        "tendency": tendency_of(values, behavior_count(session, save_id))[1],
        "mood_label": events.mood_label_of(flags, absolute),
        "virtual": {
            "absolute_minutes": absolute,
            **split,
            "label": clock.time_label(absolute),
        },
        "attributes": attrs,
        "money": money,
        "active_scene": scenes.public_active(active_flag),
        "recent_events": recent_events,
        "manual_events": [
            item for item in action_items if item.get("category") == "manual"
        ],
        "work_actions": [
            item for item in action_items if item.get("category") == "work"
        ],
        "wallet_flows": _wallet_flows(session, save_id),
    }


@router.get("/api/saves/{save_id}/messages")
def list_messages(
    save_id: int,
    limit: int = Query(default=50, ge=1, le=MESSAGES_MAX_LIMIT),
    before_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
):
    get_save_or_error(session, save_id)
    query = select(Message).where(Message.save_id == save_id)
    if before_id is not None:
        query = query.where(Message.id < before_id)
    rows = session.scalars(
        query.order_by(Message.id.desc()).limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "meta": m.meta or {},
                "game_minutes_at": m.game_minutes_at,
                "created_at": m.created_at,
            }
            for m in rows
        ],
        "has_more": has_more,
    }
