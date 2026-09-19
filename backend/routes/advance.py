"""
显式时间推进 — 调试推进面板与动作共用的推进入口（PLAN 5.4 / 第 7 节）。

推进统一走事件引擎 settle_time：属性 tick → 跨日随机判定 → 事件触发。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import TIME_MAX_JUMP_HOURS
from db import get_session
from game import clock, conversation, events
from helpers import (
    error,
    get_save_or_error,
    load_attr_values,
    require_chat_idle,
    save_settle_lock,
)
from orm import AttributeDef, Message, Save
from schemas import AdvanceIn

router = APIRouter(tags=["advance"])

MAX_TARGET_DAYS = 60


def _resolve_target(now_abs: int, target: dict) -> int:
    """把 {month, day, hour, minute} 解析为绝对虚拟分钟（必要时进入下一年）。"""
    try:
        month = int(target.get("month", 1))
        day = int(target.get("day", 1))
        hour = int(target.get("hour", 0))
        minute = int(target.get("minute", 0))
    except (TypeError, ValueError):
        error("invalid_target", "目标时刻格式不正确", 400)
    if not (1 <= month <= 12 and 1 <= day <= clock.MONTH_DAYS):
        error("invalid_target", "目标月日超出虚拟日历范围（1-12 月 / 1-30 日）", 400)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        error("invalid_target", "目标时刻超出 00:00 - 23:59 范围", 400)
    base_year = (int(now_abs) // clock.YEAR_MINUTES) * clock.YEAR_MINUTES

    def at(year_base: int) -> int:
        return (
            year_base
            + (month - 1) * clock.MONTH_MINUTES
            + (day - 1) * clock.DAY_MINUTES
            + hour * 60
            + minute
        )

    candidate = at(base_year)
    if candidate <= now_abs:
        candidate = at(base_year + clock.YEAR_MINUTES)
    return candidate


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "meta": message.meta or {},
        "game_minutes_at": message.game_minutes_at,
    }


def _advance_and_settle(session: Session, save: Save, delta: int, source: str) -> dict:
    """按增量推进并结算，写入时间说明 system 消息；返回统一结果结构。"""
    settings = save.settings or {}
    old_game = int(save.game_minutes)
    values = load_attr_values(session, save.id)
    defs = list(session.scalars(select(AttributeDef)))
    target_game = old_game + max(0, int(delta))
    settled = events.settle_time(
        session, save, defs, values, target_game, source=source
    )
    rotated = conversation.after_action(
        session,
        save,
        defs,
        values,
        time_moved=int(save.game_minutes) > old_game,
        source=source,
    )
    session.commit()
    conversation.spawn_summary_if_needed(session, save.id, rotated["summarize"])
    new_abs = clock.absolute_minutes(save.game_minutes, settings)
    virtual = {
        "absolute_minutes": new_abs,
        **clock.split(new_abs),
        "label": clock.time_label(new_abs),
    }
    changes = settled["ordered_changes"]
    random_events = [
        {
            "key": item["key"],
            "name": item["name"],
            "category": item["category"],
            "content": item["content"],
            "message_id": item["message_id"],
            "advance_minutes": item["advance_minutes"],
        }
        for item in rotated["random"]
    ]
    return {
        "game_minutes": save.game_minutes,
        "advance_minutes": int(save.game_minutes) - old_game,
        "virtual": virtual,
        "ticks": settled["tick_changes"],
        "changes": changes,
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
        ]
        + random_events,
        "messages": list(settled["messages"]) + list(rotated["messages"]),
        "conversation_ended": rotated["ended"],
    }


@router.post("/api/saves/{save_id}/advance")
def advance(save_id: int, req: AdvanceIn, session: Session = Depends(get_session)):
    require_chat_idle(save_id)
    with save_settle_lock(save_id):
        save = get_save_or_error(session, save_id)
        settings = save.settings or {}
        now_abs = clock.absolute_minutes(save.game_minutes, settings)
        modes = [x for x in (req.minutes, req.period, req.target) if x is not None]
        if len(modes) != 1:
            error("invalid_advance", "请只指定一种推进方式：minutes / period / target", 400)

        if req.minutes is not None:
            delta = min(int(req.minutes), TIME_MAX_JUMP_HOURS * 60)
        elif req.period is not None:
            target_abs = clock.next_period_start(now_abs, req.period.strip())
            if target_abs is None:
                error("invalid_period", f"未知时段：{req.period}", 400)
            delta = target_abs - now_abs
        else:
            target_abs = _resolve_target(now_abs, req.target or {})
            delta = target_abs - now_abs
            if delta <= 0:
                error("invalid_target", "目标时刻必须晚于当前虚拟时间", 400)
            if delta > MAX_TARGET_DAYS * clock.DAY_MINUTES:
                error("invalid_target", f"目标时刻过远（最多 {MAX_TARGET_DAYS} 天）", 400)

        return _advance_and_settle(session, save, delta, "advance")


@router.get("/api/saves/{save_id}/clock")
def get_clock(save_id: int, session: Session = Depends(get_session)):
    """时钟面板元数据：当前时刻、可选时段与推进上限。"""
    save = get_save_or_error(session, save_id)
    settings = save.settings or {}
    abs_now = clock.absolute_minutes(save.game_minutes, settings)
    names = {
        "dawn": "清晨",
        "morning": "上午",
        "noon": "中午",
        "afternoon": "下午",
        "evening": "傍晚",
        "night": "晚上",
        "late_night": "深夜",
    }
    return {
        "game_minutes": save.game_minutes,
        "absolute_minutes": abs_now,
        "label": clock.full_label(abs_now),
        "game_day": clock.game_day_of(save.game_minutes, settings),
        "periods": [
            {"key": key, "name": names.get(key, key)} for key in clock.period_keys()
        ],
        "max_jump_minutes": TIME_MAX_JUMP_HOURS * 60,
    }
