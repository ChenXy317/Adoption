"""
事件历史与手动事件 — 事件日志查询与 manual 触发（PLAN 5.3 / 第 7 节）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_session
from game import clock, events
from game.attributes import apply_effects
from helpers import (
    LOOPBACK_HOSTS,
    error,
    get_save_or_error,
    load_attr_values,
    require_chat_idle,
    save_settle_lock,
)
from orm import AttributeDef, EventDef, EventLog, Message

router = APIRouter(tags=["events"])


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "meta": message.meta or {},
        "game_minutes_at": message.game_minutes_at,
    }


@router.get("/api/saves/{save_id}/events")
def list_events(
    save_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    save = get_save_or_error(session, save_id)
    rows = session.execute(
        select(EventLog, EventDef.name)
        .outerjoin(EventDef, EventLog.event_id == EventDef.id)
        .where(EventLog.save_id == save_id)
        .order_by(EventLog.id.desc())
        .limit(limit)
    ).all()
    items = []
    for log, def_name in rows:
        meta = log.meta or {}
        abs_at = int(log.game_minutes_at or 0)
        items.append({
            "id": log.id,
            "event_key": meta.get("key", ""),
            "name": meta.get("name") or def_name or "事件",
            "category": meta.get("category", ""),
            "content": log.content,
            "meta": meta,
            "game_minutes_at": abs_at,
            "virtual_label": clock.time_label(abs_at),
            "triggered_at": log.triggered_at,
        })
    return {"events": items}


@router.post("/api/saves/{save_id}/events/{event_key}/trigger")
def trigger_manual(
    save_id: int,
    event_key: str,
    request: Request,
    debug: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    """手动触发（行动菜单）；debug=true 时允许任意分类并跳过条件/余额校验（仅本机）。"""
    if debug:
        host = request.client.host if request.client else ""
        if host not in LOOPBACK_HOSTS:
            error("debug_forbidden", "调试触发仅允许本机调用", 403)
    require_chat_idle(save_id)
    with save_settle_lock(save_id):
        save = get_save_or_error(session, save_id)
        event = session.scalar(select(EventDef).where(EventDef.key == event_key))
        if event is None:
            error("event_not_found", f"事件不存在：{event_key}", 404)
        if event.category not in ("manual", "work") and not debug:
            error("not_manual", "该事件不是手动事件，无法从行动菜单触发", 400)

        settings = save.settings or {}
        defs = list(session.scalars(select(AttributeDef)))
        defs_map = {d.key: d for d in defs}
        values = load_attr_values(session, save_id)
        triggered_ids, last_at = events.load_event_stats(session, save_id)
        now_abs = clock.absolute_minutes(save.game_minutes, settings)
        since = {key: max(0, now_abs - at) for key, at in last_at.items()}
        ctx = events.build_context(session, save, values, minutes_since=since)
        if not debug:
            ok, reason = events.availability(
                event,
                ctx,
                triggered=event.id in triggered_ids,
                minutes_since=since.get(event.key),
                allow_chance=False,
            )
            if not ok:
                error(
                    "event_locked",
                    events.MANUAL_REASON_TEXT.get(reason, "当前不可用"),
                    409,
                )
            ok, reason = events.check_cost(values, event.cost or {})
            if not ok:
                error("insufficient_money", "金钱不足，无法承担这项花费", 400)

        cost = event.cost or {}
        try:
            cost_money = max(0.0, float(cost.get("money") or 0))
        except (TypeError, ValueError):
            cost_money = 0.0
        try:
            cost_time = max(0, int(cost.get("time_minutes") or 0))
        except (TypeError, ValueError):
            cost_time = 0
        cost_changes: list[dict] = []
        if cost_money:
            updated, cost_changes = apply_effects(
                defs_map, values, {"money": -cost_money}
            )
            values.update(updated)
            events.write_changes(session, save_id, values, cost_changes)

        if debug:
            source = "debug"
        elif event.category == "work":
            source = "work"
        else:
            source = "manual"

        old_game = int(save.game_minutes)
        result = events.apply_event(
            session,
            save,
            event,
            ctx,
            values,
            defs_map,
            source=source,
            extra_advance=cost_time,
            extra_meta={"cost": cost, "cost_attrs": cost_changes},
        )
        settled = events.settle_time(
            session,
            save,
            defs,
            values,
            save.game_minutes + result["advance_minutes"],
            source=source,
            exclude_events={event.key},
        )
        note = None
        if int(save.game_minutes) > old_game:
            note = events.write_time_note(session, save)
        session.commit()

        new_abs = clock.absolute_minutes(save.game_minutes, settings)
        virtual = {
            "absolute_minutes": new_abs,
            **clock.split(new_abs),
            "label": clock.time_label(new_abs),
        }
        changes = cost_changes + result["attrs"] + settled["ordered_changes"]
        messages = [result["message"], *settled["messages"]]
        if note is not None:
            messages.append(_message_dict(note))
        return {
            "event": {
                "key": result["key"],
                "name": result["name"],
                "category": result["category"],
                "content": result["content"],
                "message_id": result["message_id"],
            },
            "game_minutes": save.game_minutes,
            "advance_minutes": int(save.game_minutes) - old_game,
            "virtual": virtual,
            "changes": changes,
            "ticks": settled["tick_changes"],
            "events": [
                {
                    "key": item["key"],
                    "name": item["name"],
                    "category": item["category"],
                    "content": item["content"],
                    "message_id": item["message_id"],
                    "advance_minutes": item["advance_minutes"],
                }
                for item in settled["triggered"]
            ],
            "messages": messages,
        }
