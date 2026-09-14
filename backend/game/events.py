"""
事件引擎 — 条件求值、三类事件触发与时间推进结算（PLAN 5.3 / 5.4）。

- 纯函数区：EvalContext / evaluate / availability / check_cost / roll_chance
- DB 区：上下文装载、事件落库与效果应用、settle_time 时间推进结算

随机事件在每个游戏日开始时判定一次（结果记 save_flags.random_rolls 防重复），
命中后当天满足全部条件（含时段/日期）时注入。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import EVENT_MAX_PER_SETTLEMENT, TIME_MAX_JUMP_HOURS
from game import clock
from game.attributes import apply_effects, apply_ticks
from orm import AttributeDef, AttributeValue, EventDef, EventLog, Message, Save, SaveFlag

# 每日判定阶段忽略的时段/日期类条件（留给注入阶段求值）
ROLL_EXCLUDED_TYPES = {"period", "date", "hour"}


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare(op: str, left, right) -> bool:
    """通用比较；数值优先按数值比较，另支持 contains / in / truthy。"""
    op = str(op or "==").strip()
    if op in ("truthy", "exists"):
        return bool(left)
    if op == "contains":
        try:
            return right in (left or [])
        except TypeError:
            return False
    if op == "in":
        try:
            return left in (right or [])
        except TypeError:
            return False
    left_num, right_num = _number(left), _number(right)
    if left_num is not None and right_num is not None:
        left, right = left_num, right_num
    try:
        if op == ">=":
            return left >= right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == "<":
            return left < right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
    except TypeError:
        return False
    return False


@dataclass
class EvalContext:
    """条件求值的只读快照。"""

    attrs: dict[str, float] = field(default_factory=dict)
    flags: dict[str, object] = field(default_factory=dict)
    game_day: int = 1
    month: int = 1
    day: int = 1
    hour: int = 0
    minute: int = 0
    period: str = ""
    absolute: int = 0
    minutes_since: dict[str, int | None] = field(default_factory=dict)

    def attr(self, key) -> float:
        return float(self.attrs.get(str(key), 0.0))


def evaluate(
    condition,
    ctx: EvalContext,
    *,
    rng: random.Random | None = None,
    allow_chance: bool = True,
    skip_types: set[str] | None = None,
) -> bool:
    """递归求值条件 JSON；all/any/not + 叶子类型 + 根级 chance。"""
    if condition is None or condition is True or condition == {}:
        return True
    if condition is False:
        return False
    if isinstance(condition, (list, tuple)):
        return all(
            evaluate(c, ctx, rng=rng, allow_chance=allow_chance, skip_types=skip_types)
            for c in condition
        )
    if not isinstance(condition, dict):
        return False
    for group in ("all", "any"):
        if group in condition:
            items = condition.get(group) or []
            results = [
                evaluate(c, ctx, rng=rng, allow_chance=allow_chance, skip_types=skip_types)
                for c in items
            ]
            if group == "all" and not all(results):
                return False
            if group == "any" and not any(results):
                return False
    if "not" in condition:
        if evaluate(
            condition.get("not"), ctx, rng=rng, allow_chance=allow_chance,
            skip_types=skip_types,
        ):
            return False
    if "chance" in condition and allow_chance:
        chance = _number(condition.get("chance"))
        if chance is None or chance <= 0:
            return False
        if chance < 1:
            if rng is None or rng.random() >= chance:
                return False
    if "type" in condition:
        return _leaf(condition, ctx, skip_types=skip_types)
    return True


def _leaf(cond: dict, ctx: EvalContext, *, skip_types: set[str] | None = None) -> bool:
    kind = str(cond.get("type") or "").strip()
    if skip_types and kind in skip_types:
        return True
    op = cond.get("op") or "=="
    if kind == "attr":
        return compare(op, ctx.attr(cond.get("key")), cond.get("value"))
    if kind == "flag":
        value = ctx.flags.get(str(cond.get("key")))
        if "value" not in cond and "op" not in cond:
            return bool(value)
        return compare(op, value, cond.get("value"))
    if kind == "game_day":
        return compare(op, ctx.game_day, cond.get("value"))
    if kind == "period":
        raw = cond.get("in", cond.get("value"))
        wanted = raw if isinstance(raw, (list, tuple)) else [raw]
        return ctx.period in {str(x) for x in wanted}
    if kind == "date":
        if "in" in cond:
            return any(
                _date_match(item, ctx)
                for item in (cond.get("in") or [])
                if isinstance(item, dict)
            )
        return _date_match(cond, ctx)
    if kind == "since_event":
        since = ctx.minutes_since.get(str(cond.get("key") or ""))
        if since is None:
            return True
        return compare(op, since, cond.get("value"))
    return False


def _date_match(cond: dict, ctx: EvalContext) -> bool:
    month, day = cond.get("month"), cond.get("day")
    if month is not None and int(month) != ctx.month:
        return False
    if day is not None and int(day) != ctx.day:
        return False
    return month is not None or day is not None


def roll_chance(trigger: dict | None, rng: random.Random) -> bool:
    """随机事件的每日概率判定；未配置 chance 视为必定命中。"""
    chance = _number((trigger or {}).get("chance"))
    if chance is None:
        return True
    if chance <= 0:
        return False
    if chance >= 1:
        return True
    return rng.random() < chance


def availability(
    event: EventDef,
    ctx: EvalContext,
    *,
    triggered: bool,
    minutes_since: int | None,
    rng: random.Random | None = None,
    allow_chance: bool = False,
    skip_types: set[str] | None = None,
) -> tuple[bool, str]:
    """事件可用性：启用、once、冷却、条件。返回 (是否可用, 原因码)。"""
    if not event.enabled:
        return False, "disabled"
    if event.once and triggered:
        return False, "used"
    cooldown = int(event.cooldown_minutes or 0)
    if cooldown > 0 and minutes_since is not None and minutes_since < cooldown:
        return False, "cooldown"
    if not evaluate(
        event.trigger or {},
        ctx,
        rng=rng,
        allow_chance=allow_chance,
        skip_types=skip_types,
    ):
        return False, "locked"
    return True, "ok"


def check_cost(values: dict[str, float], cost: dict | None) -> tuple[bool, str]:
    """手动事件 cost 校验（金钱余额；时间成本无需校验）。"""
    money = _number((cost or {}).get("money"))
    if money and money > 0 and float(values.get("money", 0.0)) < money:
        return False, "insufficient_money"
    return True, "ok"


def _raw_flag(value):
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def load_flags(session: Session, save_id: int) -> dict[str, object]:
    rows = session.scalars(select(SaveFlag).where(SaveFlag.save_id == save_id))
    return {r.key: _raw_flag(r.value) for r in rows}


def set_flag(session: Session, save_id: int, key: str, value) -> None:
    payload = value if isinstance(value, dict) else {"value": value}
    row = session.get(SaveFlag, (save_id, key))
    if row is None:
        session.add(SaveFlag(save_id=save_id, key=key, value=payload))
    else:
        row.value = payload


def load_event_stats(session: Session, save_id: int) -> tuple[set[int], dict[str, int]]:
    """一次查询取回：已触发事件 id 集合 + 各事件最近触发时刻（绝对虚拟分钟）。"""
    rows = session.execute(
        select(EventDef.id, EventDef.key, func.max(EventLog.game_minutes_at))
        .join(EventLog, EventLog.event_id == EventDef.id)
        .where(EventLog.save_id == save_id, EventLog.status == "triggered")
        .group_by(EventDef.id, EventDef.key)
    ).all()
    triggered: set[int] = set()
    last_at: dict[str, int] = {}
    for event_id, key, at in rows:
        triggered.add(event_id)
        last_at[key] = int(at or 0)
    return triggered, last_at


def _since_map(last_at: dict[str, int], now_abs: int) -> dict[str, int]:
    return {key: max(0, now_abs - at) for key, at in last_at.items()}


def build_context(
    session: Session,
    save: Save,
    values: dict[str, float],
    *,
    minutes_since: dict[str, int | None] | None = None,
    at_abs: int | None = None,
) -> EvalContext:
    settings = save.settings or {}
    absolute = (
        at_abs if at_abs is not None
        else clock.absolute_minutes(save.game_minutes, settings)
    )
    split = clock.split(absolute)
    game_day = (
        clock.day_index(absolute)
        - clock.day_index(clock.start_offset(settings))
        + 1
    )
    return EvalContext(
        attrs=dict(values),
        flags=load_flags(session, save.id),
        game_day=game_day,
        month=split["month"],
        day=split["day"],
        hour=split["hour"],
        minute=split["minute"],
        period=split["period_key"],
        absolute=absolute,
        minutes_since=dict(minutes_since or {}),
    )


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "meta": message.meta or {},
        "game_minutes_at": message.game_minutes_at,
    }


def write_changes(session: Session, save_id: int, values: dict, changes: list[dict]) -> None:
    """把属性变化写入 attribute_values；缺行时自动补建（属性定义晚于存档创建）。"""
    for change in changes:
        key = change["key"]
        if key not in values:
            continue
        row = session.get(AttributeValue, (save_id, key))
        if row is None:
            session.add(
                AttributeValue(save_id=save_id, attr_key=key, value=values[key])
            )
        else:
            row.value = values[key]


def apply_event(
    session: Session,
    save: Save,
    event: EventDef,
    ctx: EvalContext,
    values: dict[str, float],
    defs_map: dict[str, AttributeDef],
    *,
    source: str = "fixed",
    extra_advance: int = 0,
) -> dict:
    """应用事件效果并落 event_logs + role=event 消息；返回触发结果。"""
    effects = event.effects or {}
    attr_changes: list[dict] = []
    if effects.get("attrs"):
        updated, attr_changes = apply_effects(defs_map, values, effects.get("attrs"))
        values.update(updated)
        write_changes(session, save.id, values, attr_changes)
    flags = effects.get("flags") or {}
    for key, value in flags.items():
        set_flag(session, save.id, str(key), value)
    for key in effects.get("unlock_events") or []:
        set_flag(session, save.id, f"event_unlocked:{key}", True)
    advance = _number(effects.get("advance_minutes")) or 0
    advance = max(0, int(advance)) + max(0, int(extra_advance))
    advance = min(advance, TIME_MAX_JUMP_HOURS * 60)

    content = (event.prompt_template or "").strip() or event.name
    log = EventLog(
        save_id=save.id,
        event_id=event.id,
        status="triggered",
        content=content,
        meta={
            "key": event.key,
            "name": event.name,
            "category": event.category,
            "source": source,
            "attrs": attr_changes,
            "flags": flags,
            "advance_minutes": advance,
        },
        game_minutes_at=ctx.absolute,
    )
    session.add(log)
    session.flush()
    message = Message(
        save_id=save.id,
        role="event",
        content=content,
        meta={
            "event_key": event.key,
            "event_name": event.name,
            "category": event.category,
            "log_id": log.id,
        },
        game_minutes_at=ctx.absolute,
    )
    session.add(message)
    session.flush()

    ctx.attrs = dict(values)
    for key, value in flags.items():
        ctx.flags[str(key)] = value
    return {
        "key": event.key,
        "name": event.name,
        "category": event.category,
        "content": content,
        "log_id": log.id,
        "message_id": message.id,
        "message": _message_dict(message),
        "attrs": attr_changes,
        "flags": flags,
        "advance_minutes": advance,
        "start_scene": str(effects.get("start_scene") or "").strip() or None,
    }


def _advance_core(
    session: Session,
    save: Save,
    defs_map: dict[str, AttributeDef],
    values: dict[str, float],
    target_game_minutes: int,
) -> tuple[int, list[dict], list[int]]:
    """推进游戏时钟：tick 结算 + 跨日检测。返回 (实际增量, tick 变化, 跨日午夜列表)。"""
    old_game = int(save.game_minutes)
    target = max(old_game, int(target_game_minutes))
    delta = target - old_game
    if delta <= 0:
        return 0, [], []
    settings = save.settings or {}
    old_abs = clock.absolute_minutes(old_game, settings)
    new_abs = clock.absolute_minutes(target, settings)
    new_values, tick_changes = apply_ticks(defs_map, values, delta / 60.0)
    values.update(new_values)
    write_changes(session, save.id, values, tick_changes)
    save.game_minutes = target
    return delta, tick_changes, clock.day_starts_between(old_abs, new_abs)


def _random_roll_state(session: Session, save_id: int) -> dict:
    row = session.get(SaveFlag, (save_id, "random_rolls"))
    value = _raw_flag(row.value) if row is not None else {}
    return dict(value) if isinstance(value, dict) else {}


def _roll_new_days(
    session: Session,
    save: Save,
    event_defs: list[EventDef],
    values: dict[str, float],
    day_starts: list[int],
    rng: random.Random,
    triggered_ids: set[int],
    since: dict[str, int],
) -> None:
    """对每个新游戏日为随机事件做每日一次的概率判定。"""
    state = _random_roll_state(session, save.id)
    for start in day_starts:
        day = clock.day_index(start)
        ctx = build_context(session, save, values, minutes_since=since, at_abs=start)
        for event in event_defs:
            if event.category != "random":
                continue
            entry = state.get(event.key)
            if isinstance(entry, dict) and entry.get("day") == day:
                continue
            if event.once and event.id in triggered_ids:
                state[event.key] = {"day": day, "hit": False, "reason": "used"}
                continue
            ok, reason = availability(
                event,
                ctx,
                triggered=event.id in triggered_ids,
                minutes_since=since.get(event.key),
                allow_chance=False,
                skip_types=ROLL_EXCLUDED_TYPES,
            )
            hit = ok and roll_chance(event.trigger or {}, rng)
            state[event.key] = {"day": day, "hit": hit}
            if not ok:
                state[event.key]["reason"] = reason
    if day_starts:
        set_flag(session, save.id, "random_rolls", state)


def _collect_fixed(
    session: Session,
    save: Save,
    event_defs: list[EventDef],
    values: dict[str, float],
    since: dict[str, int],
    triggered_ids: set[int],
    exclude: set[str],
) -> list[EventDef]:
    ctx = build_context(session, save, values, minutes_since=since)
    picks = []
    for event in event_defs:
        if event.category != "fixed" or event.key in exclude:
            continue
        ok, _reason = availability(
            event,
            ctx,
            triggered=event.id in triggered_ids,
            minutes_since=since.get(event.key),
            allow_chance=False,
        )
        if ok:
            picks.append(event)
    return picks


def _collect_random_inject(
    session: Session,
    save: Save,
    event_defs: list[EventDef],
    values: dict[str, float],
    since: dict[str, int],
    triggered_ids: set[int],
    exclude: set[str],
) -> list[EventDef]:
    """当天随机判定命中、且此刻全部条件（含时段/日期）满足的事件。"""
    state = _random_roll_state(session, save.id)
    if not state:
        return []
    settings = save.settings or {}
    now_abs = clock.absolute_minutes(save.game_minutes, settings)
    today = clock.day_index(now_abs)
    elapsed_today = now_abs - today * clock.DAY_MINUTES
    ctx = build_context(session, save, values, minutes_since=since, at_abs=now_abs)
    picks = []
    for event in event_defs:
        if event.category != "random" or event.key in exclude:
            continue
        entry = state.get(event.key)
        if not isinstance(entry, dict) or not entry.get("hit"):
            continue
        if entry.get("day") != today:
            continue
        last_since = since.get(event.key)
        if last_since is not None and last_since <= elapsed_today:
            entry["hit"] = False
            continue
        ok, reason = availability(
            event,
            ctx,
            triggered=event.id in triggered_ids,
            minutes_since=last_since,
            allow_chance=False,
        )
        if ok:
            picks.append(event)
        elif reason == "used":
            entry["hit"] = False
    return picks


def settle_time(
    session: Session,
    save: Save,
    defs: list[AttributeDef],
    values: dict[str, float],
    target_game_minutes: int,
    *,
    source: str = "advance",
    rng: random.Random | None = None,
    state_scene: dict | None = None,
) -> dict:
    """推进到目标游戏分钟并结算：tick → 跨日随机判定 → 事件触发 → 场景生命周期。

    同一事务内完成，最终 commit 由调用方负责。values 会被就地更新为最终属性值。
    """
    rng = rng or random.Random()
    defs_map = {d.key: d for d in defs}
    event_defs = list(
        session.scalars(
            select(EventDef)
            .where(EventDef.enabled.is_(True))
            .order_by(EventDef.priority.desc(), EventDef.id)
        )
    )
    triggered_ids, last_at = load_event_stats(session, save.id)
    triggered_results: list[dict] = []
    tick_changes: list[dict] = []
    pending_days: list[int] = []
    forced_scene: str | None = None

    delta, ticks, crossed = _advance_core(
        session, save, defs_map, values, target_game_minutes
    )
    tick_changes.extend(ticks)
    pending_days.extend(crossed)

    if any(event.category == "random" for event in event_defs):
        today = clock.day_index(
            clock.absolute_minutes(save.game_minutes, save.settings or {})
        )
        state = _random_roll_state(session, save.id)
        rolled_today = any(
            isinstance(entry, dict) and entry.get("day") == today
            for entry in state.values()
        )
        today_start = today * clock.DAY_MINUTES
        if not rolled_today and today_start not in pending_days:
            pending_days.insert(0, today_start)

    exclude: set[str] = set()
    rounds = 0
    while rounds < 4 and len(triggered_results) < EVENT_MAX_PER_SETTLEMENT:
        rounds += 1
        now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
        since = _since_map(last_at, now_abs)
        if pending_days:
            _roll_new_days(
                session, save, event_defs, values, pending_days, rng, triggered_ids, since
            )
            pending_days = []
        candidates = _collect_fixed(
            session, save, event_defs, values, since, triggered_ids, exclude
        )
        candidates += _collect_random_inject(
            session, save, event_defs, values, since, triggered_ids, exclude
        )
        if not candidates:
            break
        seen: set[str] = set()
        for event in candidates:
            if event.key in seen or event.key in exclude:
                continue
            seen.add(event.key)
            if len(triggered_results) >= EVENT_MAX_PER_SETTLEMENT:
                break
            now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
            ctx = build_context(
                session, save, values, minutes_since=_since_map(last_at, now_abs)
            )
            result = apply_event(
                session, save, event, ctx, values, defs_map, source=source
            )
            triggered_results.append(result)
            exclude.add(event.key)
            triggered_ids.add(event.id)
            last_at[event.key] = ctx.absolute
            if result["start_scene"] and forced_scene is None:
                forced_scene = result["start_scene"]
            if result["advance_minutes"] > 0:
                _extra, extra_ticks, extra_crossed = _advance_core(
                    session,
                    save,
                    defs_map,
                    values,
                    save.game_minutes + result["advance_minutes"],
                )
                tick_changes.extend(extra_ticks)
                pending_days.extend(extra_crossed)

    from game import scenes

    scene_result = scenes.settle_scenes(
        session,
        save,
        defs_map,
        values,
        source=source,
        state_scene=state_scene,
        forced_key=forced_scene,
    )
    scene_advance = sum(
        int(entry["advance_minutes"])
        for entry in (scene_result["entered"], scene_result["ended"])
        if entry and entry.get("advance_minutes")
    )
    if scene_advance > 0:
        _extra, extra_ticks, _extra_crossed = _advance_core(
            session, save, defs_map, values, save.game_minutes + scene_advance
        )
        tick_changes.extend(extra_ticks)

    now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
    scene_messages = [
        entry["message"]
        for entry in (scene_result["entered"], scene_result["ended"])
        if entry and entry.get("message")
    ]
    return {
        "delta": delta,
        "tick_changes": tick_changes,
        "triggered": triggered_results,
        "messages": [r["message"] for r in triggered_results] + scene_messages,
        "game_minutes": save.game_minutes,
        "absolute_minutes": now_abs,
        "scene": scene_result,
    }


def manual_candidates(
    session: Session,
    save: Save,
    values: dict[str, float],
) -> list[dict]:
    """行动菜单可用的手动事件清单（含可用性与禁用原因）。"""
    event_defs = list(
        session.scalars(
            select(EventDef)
            .where(EventDef.category == "manual", EventDef.enabled.is_(True))
            .order_by(EventDef.priority.desc(), EventDef.id)
        )
    )
    triggered_ids, last_at = load_event_stats(session, save.id)
    now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
    since = _since_map(last_at, now_abs)
    ctx = build_context(session, save, values, minutes_since=since)
    items = []
    for event in event_defs:
        ok, reason = availability(
            event,
            ctx,
            triggered=event.id in triggered_ids,
            minutes_since=since.get(event.key),
            allow_chance=False,
        )
        cost = event.cost or {}
        if ok:
            ok, reason = check_cost(values, cost)
        items.append({
            "key": event.key,
            "name": event.name,
            "cost": cost,
            "available": ok,
            "reason": reason if not ok else "ok",
            "once": bool(event.once),
            "used": event.once and event.id in triggered_ids,
        })
    return items


MANUAL_REASON_TEXT = {
    "ok": "",
    "locked": "条件未满足",
    "cooldown": "冷却中",
    "used": "已完成",
    "disabled": "已停用",
    "insufficient_money": "金钱不足",
}


def recent_events(session: Session, save: Save, *, window_minutes: int, limit: int = 3) -> list[dict]:
    """最近窗口内触发的普通事件（用于 prompt 情境块）。"""
    settings = save.settings or {}
    now_abs = clock.absolute_minutes(save.game_minutes, settings)
    rows = list(
        session.scalars(
            select(EventLog)
            .where(
                EventLog.save_id == save.id,
                EventLog.game_minutes_at >= now_abs - int(window_minutes),
            )
            .order_by(EventLog.id.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return [
        {
            "key": (row.meta or {}).get("key", ""),
            "name": (row.meta or {}).get("name", ""),
            "category": (row.meta or {}).get("category", ""),
            "content": row.content,
        }
        for row in rows
    ]
