"""
对话轮次 — 手动事件或显式推进时间后结束当前对话、总结，并打开新对话。

新对话开头注入当天已判定命中的随机事件。
"""
from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import EVENT_MAX_PER_SETTLEMENT
from game import clock, events, memory
from orm import AttributeDef, EventDef, Message, Save

CONV_FLAG = "conversation"


def _raw_state(session: Session, save_id: int) -> dict:
    flags = events.load_flags(session, save_id)
    raw = flags.get(CONV_FLAG)
    return dict(raw) if isinstance(raw, dict) else {}


def started_after_id(session: Session, save_id: int) -> int:
    """当前对话只包含 id 大于该值的消息。"""
    try:
        return max(0, int(_raw_state(session, save_id).get("started_after_id") or 0))
    except (TypeError, ValueError):
        return 0


def _set_started_after(session: Session, save_id: int, message_id: int) -> None:
    state = _raw_state(session, save_id)
    try:
        conv_id = int(state.get("id") or 0) + 1
    except (TypeError, ValueError):
        conv_id = 1
    events.set_flag(
        session,
        save_id,
        CONV_FLAG,
        {"id": conv_id, "started_after_id": int(message_id)},
    )


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "meta": message.meta or {},
        "game_minutes_at": message.game_minutes_at,
    }


def _has_roles(
    session: Session, save_id: int, after_id: int, roles: tuple[str, ...]
) -> bool:
    return (
        session.scalar(
            select(func.count(Message.id)).where(
                Message.save_id == save_id,
                Message.id > after_id,
                Message.role.in_(roles),
            )
        )
        or 0
    ) > 0


def close_current(session: Session, save: Save) -> dict:
    """若当前对话有消息，写入结束标记并推进对话起点。"""
    after_id = started_after_id(session, save.id)
    has_any = (
        session.scalar(
            select(func.count(Message.id)).where(
                Message.save_id == save.id,
                Message.id > after_id,
            )
        )
        or 0
    ) > 0
    if not has_any:
        return {"ended": False, "summarize": False, "message": None}
    abs_now = clock.absolute_minutes(save.game_minutes, save.settings or {})
    row = Message(
        save_id=save.id,
        role="system",
        content="这一段对话结束了。",
        meta={"kind": "conversation_end"},
        game_minutes_at=abs_now,
    )
    session.add(row)
    session.flush()
    _set_started_after(session, save.id, row.id)
    summarize = _has_roles(session, save.id, after_id, ("user", "assistant"))
    return {
        "ended": True,
        "summarize": summarize,
        "message": _message_dict(row),
    }


def inject_due_random(
    session: Session,
    save: Save,
    defs: list[AttributeDef],
    values: dict[str, float],
    *,
    source: str = "conversation",
) -> list[dict]:
    """把当天已判定命中、此刻条件满足的随机事件注入到新对话开头。"""
    rng = random.Random()
    defs_map = {d.key: d for d in defs}
    event_defs = list(
        session.scalars(
            select(EventDef)
            .where(EventDef.enabled.is_(True))
            .order_by(EventDef.priority.desc(), EventDef.id)
        )
    )
    triggered_ids, last_at = events.load_event_stats(session, save.id)
    now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
    since = events._since_map(last_at, now_abs)
    today = clock.day_index(now_abs)
    state = events._random_roll_state(session, save.id)
    rolled_today = any(
        isinstance(entry, dict) and entry.get("day") == today
        for entry in state.values()
    )
    if not rolled_today:
        events._roll_new_days(
            session,
            save,
            event_defs,
            values,
            [today * clock.DAY_MINUTES],
            rng,
            triggered_ids,
            since,
        )
        since = events._since_map(last_at, now_abs)
    picks = events._collect_random_inject(
        session, save, event_defs, values, since, triggered_ids, set()
    )
    results: list[dict] = []
    exclude: set[str] = set()
    for event in picks:
        if event.key in exclude:
            continue
        if len(results) >= EVENT_MAX_PER_SETTLEMENT:
            break
        now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
        ctx = events.build_context(
            session, save, values, minutes_since=events._since_map(last_at, now_abs)
        )
        result = events.apply_event(
            session, save, event, ctx, values, defs_map, source=source
        )
        results.append(result)
        exclude.add(event.key)
        triggered_ids.add(event.id)
        last_at[event.key] = ctx.absolute
    return results


def after_action(
    session: Session,
    save: Save,
    defs: list[AttributeDef],
    values: dict[str, float],
    *,
    time_moved: bool,
    source: str,
) -> dict:
    """结束当前对话（如有），写下时间说明，再以随机事件打开新对话。"""
    closed = close_current(session, save)
    note = None
    if time_moved:
        note = events.write_time_note(session, save)
    injected = inject_due_random(session, save, defs, values, source=source)
    messages: list[dict] = []
    if closed.get("message"):
        messages.append(closed["message"])
    if note is not None:
        messages.append(_message_dict(note))
    for item in injected:
        if item.get("message"):
            messages.append(item["message"])
    return {
        "summarize": bool(closed.get("summarize")),
        "ended": bool(closed.get("ended")),
        "random": injected,
        "messages": messages,
    }


def spawn_summary_if_needed(session: Session, save_id: int, summarize: bool) -> None:
    """事务提交后：若本轮需要总结则排队并后台执行。"""
    if not summarize:
        return
    if memory.queue_summary(session, save_id, force=True):
        memory.spawn_background(save_id)
