"""
存档状态与消息历史 — 前端主界面数据来源（PLAN 第 7 节）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_session
from game import clock
from helpers import (
    attribute_items,
    character_dict,
    get_save_or_error,
    load_attr_values,
)
from orm import AttributeDef, Character, Message, SaveFlag

router = APIRouter(tags=["state"])

MESSAGES_MAX_LIMIT = 200


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
    character = session.scalar(
        select(Character).where(Character.save_id == save_id)
    )
    active_flag = session.get(SaveFlag, (save_id, "active_scene"))
    return {
        "save": {
            "id": save.id,
            "name": save.name,
            "status": save.status,
            "model_key": save.model_key,
            "game_minutes": save.game_minutes,
        },
        "character": character_dict(character),
        "virtual": {
            "absolute_minutes": absolute,
            **split,
            "label": clock.time_label(absolute),
        },
        "attributes": attribute_items(defs, values),
        "money": values.get("money", 0.0),
        "active_scene": (active_flag.value if active_flag else None),
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
