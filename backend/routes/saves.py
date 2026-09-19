"""
存档 CRUD — 创建时初始化角色与属性值（PLAN 第 4 节）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from config import (
    DEFAULT_PARAMS,
    TIME_DEFAULT_ADVANCE,
    TIME_MAX_ADVANCE_PER_MESSAGE,
)
from db import get_session
from game import clock, openings
from game.attributes import clamp
from helpers import (
    character_dict,
    drop_save_lock,
    error,
    get_global_character,
    get_runtime,
    get_save_character,
    get_save_or_error,
    sanitize_settings,
)
from orm import AttributeDef, AttributeValue, Message, Save
from schemas import SaveCreate, SaveUpdate

router = APIRouter(tags=["saves"])


def save_summary(session: Session, save: Save, message_count: int | None = None) -> dict:
    character = get_save_character(session, save)
    if message_count is None:
        message_count = session.scalar(
            select(func.count(Message.id)).where(Message.save_id == save.id)
        ) or 0
    settings = save.settings or {}
    return {
        "id": save.id,
        "name": save.name,
        "status": save.status,
        "model_key": save.model_key,
        "game_minutes": save.game_minutes,
        "virtual_time": clock.time_label(
            clock.absolute_minutes(save.game_minutes, settings)
        ),
        "character": character_dict(character),
        "message_count": message_count,
        "created_at": save.created_at,
        "updated_at": save.updated_at,
    }


def init_attribute_values(
    session: Session, save_id: int, overrides: dict | None = None
) -> None:
    overrides = overrides if isinstance(overrides, dict) else {}
    defs = session.scalars(select(AttributeDef).where(AttributeDef.enabled.is_(True)))
    for d in defs:
        raw = overrides.get(d.key, d.default_value)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = d.default_value
        session.add(
            AttributeValue(
                save_id=save_id,
                attr_key=d.key,
                value=clamp(value, d.min, d.max),
            )
        )


@router.get("/api/openings")
def list_openings():
    return openings.public_list()


@router.get("/api/saves")
def list_saves(session: Session = Depends(get_session)):
    saves = session.scalars(select(Save).order_by(Save.id)).all()
    ids = [s.id for s in saves]
    counts: dict[int, int] = {}
    if ids:
        counts = dict(
            session.execute(
                select(Message.save_id, func.count(Message.id))
                .where(Message.save_id.in_(ids))
                .group_by(Message.save_id)
            ).all()
        )
    return [save_summary(session, s, counts.get(s.id, 0)) for s in saves]


@router.post("/api/saves")
def create_save(req: SaveCreate, session: Session = Depends(get_session)):
    character = get_global_character(session)
    if character is None:
        error(
            "character_required",
            "还没有女主角设定书，请先在首页创建女主角",
            400,
        )
    if req.model_key:
        get_runtime(session, req.model_key)
    opening = openings.get(req.opening_key)
    if opening is None:
        error("opening_not_found", "未知的开场阶段", 400)
    settings = {
        "calendar": openings.calendar_of(opening),
        "params": dict(DEFAULT_PARAMS),
        "content_prompt": "",
        "advance": {
            "default_minutes": TIME_DEFAULT_ADVANCE,
            "max_per_message": TIME_MAX_ADVANCE_PER_MESSAGE,
        },
        "opening": openings.snapshot(opening),
    }
    if req.settings:
        settings.update(sanitize_settings(req.settings, base=settings))
    try:
        game_minutes = max(0, int(opening.get("game_minutes") or 0))
    except (TypeError, ValueError):
        game_minutes = 0
    save = Save(
        character_id=character.id,
        name=req.name.strip(),
        model_key=req.model_key,
        game_minutes=game_minutes,
        settings=settings,
    )
    session.add(save)
    session.flush()
    init_attribute_values(session, save.id, opening.get("attrs"))
    session.flush()
    openings.apply(session, save, opening)
    session.commit()
    return save_summary(session, save)


@router.get("/api/saves/{save_id}")
def get_save(save_id: int, session: Session = Depends(get_session)):
    save = get_save_or_error(session, save_id)
    data = save_summary(session, save)
    data["settings"] = save.settings or {}
    return data


@router.patch("/api/saves/{save_id}")
def update_save(
    save_id: int, req: SaveUpdate, session: Session = Depends(get_session)
):
    save = get_save_or_error(session, save_id)
    if req.name is not None:
        save.name = req.name.strip()
    if req.model_key is not None:
        if req.model_key:
            get_runtime(session, req.model_key)
        save.model_key = req.model_key
    if req.status is not None:
        save.status = req.status.strip()
    if req.settings is not None:
        merged = {**(save.settings or {}), **req.settings}
        save.settings = sanitize_settings(merged, base=save.settings)
    session.commit()
    return save_summary(session, save)


@router.delete("/api/saves/{save_id}")
def delete_save(save_id: int, session: Session = Depends(get_session)):
    save = get_save_or_error(session, save_id)
    session.execute(delete(Save).where(Save.id == save.id))
    session.commit()
    drop_save_lock(save_id)
    return {"ok": True}
