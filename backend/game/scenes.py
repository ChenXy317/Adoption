"""
场景引擎 — 多轮场景的进入/持续/结束/结算（PLAN 5.3）。

- 纯函数区：scene_availability / should_finish / scene_block / memory_content
- DB 区：active_scene 生命周期、进入与结束结算、settle_scenes 统一入口

同一时刻仅 1 个活跃场景：无活跃场景时评估进入条件（事件 effects.start_scene
可指定候选），进入时写 save_flags.active_scene 与 scene_logs(started)；
每轮对话 turns +1，由 AI 标签 / exit 条件 / max_turns 触发结束，
结束同一事务内结算 effects、写 scene_logs(finished)、生成场景记忆并解锁 next_scenes。
"""
from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import SCENE_MEMORY_IMPORTANCE, SCENE_PROMPT_CHAR_BUDGET, TIME_MAX_JUMP_HOURS
from game import clock, events
from game.attributes import apply_effects
from orm import Memory, Message, Save, SaveFlag, SceneDef, SceneLog

ACTIVE_FLAG = "active_scene"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "meta": message.meta or {},
        "game_minutes_at": message.game_minutes_at,
    }


# ── active_scene（save_flags 中的场景生命周期标记）──

def get_active(session: Session, save_id: int) -> dict | None:
    row = session.get(SaveFlag, (save_id, ACTIVE_FLAG))
    if row is None or not isinstance(row.value, dict):
        return None
    value = row.value
    if set(value.keys()) == {"value"}:
        value = value["value"]
    return dict(value) if isinstance(value, dict) else None


def set_active(session: Session, save_id: int, active: dict) -> None:
    events.set_flag(session, save_id, ACTIVE_FLAG, active)


def clear_active(session: Session, save_id: int) -> None:
    row = session.get(SaveFlag, (save_id, ACTIVE_FLAG))
    if row is not None:
        session.delete(row)


# ── 纯函数区 ──

def scene_availability(
    scene: SceneDef,
    ctx,
    *,
    triggered: bool,
    minutes_since: int | None,
    rng: random.Random | None = None,
    allow_chance: bool = False,
) -> tuple[bool, str]:
    """场景进入可用性：启用/once/冷却/进入条件（与事件同口径）。

    triggered 指该场景已完成过（once）；minutes_since 为距上次结束的虚拟分钟。
    """
    if not scene.enabled:
        return False, "disabled"
    if scene.once and triggered:
        return False, "used"
    cooldown = int(scene.cooldown_minutes or 0)
    if cooldown > 0 and minutes_since is not None and minutes_since < cooldown:
        return False, "cooldown"
    if not events.evaluate(
        scene.enter_trigger or {}, ctx, rng=rng, allow_chance=allow_chance
    ):
        return False, "locked"
    return True, "ok"


def should_finish(
    scene: SceneDef, turns_after: int, *, ai_end: bool, exit_met: bool
) -> str | None:
    """结束判定：AI 主动收尾（min_turns 内拒绝）→ exit 条件 → 超过 max_turns 强收。"""
    if ai_end and turns_after >= max(0, int(scene.min_turns or 0)):
        return "ai"
    if exit_met:
        return "exit"
    max_turns = max(0, int(scene.max_turns or 0))
    if max_turns > 0 and turns_after > max_turns:
        return "max_turns"
    return None


def scene_block(active: dict) -> str:
    """当前场景注入 prompt 的文本块（含轮数；到达 max_turns 后追加收尾指令）。"""
    name = str(active.get("name") or active.get("key") or "场景").strip()
    goal = str(active.get("goal") or "").strip()
    setting = str(active.get("prompt") or "").strip()
    if len(setting) > SCENE_PROMPT_CHAR_BUDGET:
        setting = setting[:SCENE_PROMPT_CHAR_BUDGET] + "…"
    turns = max(0, int(active.get("turns") or 0))
    max_turns = max(0, int(active.get("max_turns") or 0))
    lines = ["# 当前场景", f"场景：{name}"]
    if setting:
        lines.append(f"场景设定：{setting}")
    if goal:
        lines.append(f"本幕目标：{goal}")
    lines.append(
        f"进度：本幕已进行 {turns} 轮，这是第 {turns + 1} 轮"
        + (f"（预计 {max_turns} 轮内收尾）" if max_turns > 0 else "")
    )
    if max_turns > 0 and turns >= max_turns:
        lines.append(
            "请在本条回复中自然地把这一幕收尾：完成目标或做出交代，"
            '并在状态标签的 scene 中输出 {"action":"end","summary":"一句话总结本幕"}。'
        )
    lines.append(
        "围绕本幕目标展开演出，保持场景连续；不要在正文里提及轮数、目标或收尾说明。"
    )
    return "\n".join(lines)


def memory_content(scene: SceneDef, summary: str) -> str:
    """场景结束写入记忆的正文（AI 总结优先，缺失时用目标兜底）。"""
    text = (summary or "").strip()
    if not text:
        goal = (scene.goal or "").strip()
        text = f"这一幕结束了（目标：{goal}）。" if goal else "这一幕结束了。"
    return f"【{scene.name}】{text}"


def brief(entry: dict | None) -> dict | None:
    """场景进入/结束结果的精简结构（用于 SSE 与接口返回）。"""
    if not entry:
        return None
    return {
        "key": entry.get("key", ""),
        "name": entry.get("name", ""),
        "goal": entry.get("goal", ""),
        "turns": entry.get("turns", 0),
        "reason": entry.get("reason", ""),
        "summary": entry.get("summary", ""),
        "log_id": entry.get("log_id"),
    }


def public_active(active: dict | None) -> dict | None:
    """对外的活跃场景结构（去掉场景设定原文）。"""
    if not active:
        return None
    return {
        "key": active.get("key", ""),
        "name": active.get("name", ""),
        "goal": active.get("goal", ""),
        "turns": int(active.get("turns") or 0),
        "min_turns": int(active.get("min_turns") or 0),
        "max_turns": int(active.get("max_turns") or 0),
        "started_game_minutes": int(active.get("started_game_minutes") or 0),
    }


# ── DB 区 ──

def load_scene_stats(
    session: Session, save_id: int
) -> tuple[set[str], dict[str, int]]:
    """已完成（finished）场景 key 集合 + 各场景最近结束时刻（绝对虚拟分钟，含中止）。"""
    done = set(
        session.scalars(
            select(SceneLog.scene_key)
            .where(SceneLog.save_id == save_id, SceneLog.status == "finished")
            .distinct()
        )
    )
    rows = session.execute(
        select(SceneLog.scene_key, func.max(SceneLog.game_minutes_at))
        .where(
            SceneLog.save_id == save_id,
            SceneLog.status.in_(("finished", "aborted")),
        )
        .group_by(SceneLog.scene_key)
    ).all()
    last_at = {key: int(at or 0) for key, at in rows}
    return done, last_at


def _latest_open_log(session: Session, save_id: int, scene_key: str) -> SceneLog | None:
    return session.scalar(
        select(SceneLog)
        .where(
            SceneLog.save_id == save_id,
            SceneLog.scene_key == scene_key,
            SceneLog.status == "started",
        )
        .order_by(SceneLog.id.desc())
        .limit(1)
    )


def enter_scene(
    session: Session,
    save: Save,
    scene: SceneDef,
    ctx,
    values: dict[str, float],
    defs_map,
    *,
    source: str = "auto",
) -> dict:
    """进入场景：扣进入花费 → 写 active 标记 → scene_logs(started) → 轻量开场消息。"""
    cost = scene.enter_cost or {}
    cost_changes: list[dict] = []
    money = _number(cost.get("money"))
    if money and money > 0:
        updated, cost_changes = apply_effects(defs_map, values, {"money": -money})
        values.update(updated)
        events.write_changes(session, save.id, values, cost_changes)
    time_cost = int(_number(cost.get("time_minutes")) or 0)
    time_cost = max(0, min(time_cost, TIME_MAX_JUMP_HOURS * 60))

    active = {
        "key": scene.key,
        "name": scene.name,
        "goal": scene.goal or "",
        "prompt": scene.scene_prompt or "",
        "turns": 0,
        "min_turns": max(0, int(scene.min_turns or 0)),
        "max_turns": max(0, int(scene.max_turns or 0)),
        "started_game_minutes": int(save.game_minutes),
        "source": source,
    }
    set_active(session, save.id, active)
    log = SceneLog(
        save_id=save.id,
        scene_key=scene.key,
        status="started",
        summary="",
        meta={"name": scene.name, "goal": scene.goal or "", "source": source},
        game_minutes_at=ctx.absolute,
    )
    session.add(log)
    session.flush()

    opening = f"【{scene.name}】" + (scene.scene_prompt or "").strip()
    message = Message(
        save_id=save.id,
        role="event",
        content=opening[:500],
        meta={
            "scene_key": scene.key,
            "scene_name": scene.name,
            "kind": "scene_start",
            "log_id": log.id,
        },
        game_minutes_at=ctx.absolute,
    )
    session.add(message)
    session.flush()
    return {
        "key": scene.key,
        "name": scene.name,
        "goal": scene.goal or "",
        "turns": 0,
        "max_turns": active["max_turns"],
        "content": opening[:500],
        "log_id": log.id,
        "message_id": message.id,
        "message": _message_dict(message),
        "attrs": cost_changes,
        "advance_minutes": time_cost,
    }


def finish_scene(
    session: Session,
    save: Save,
    scene: SceneDef,
    active: dict,
    ctx,
    values: dict[str, float],
    defs_map,
    *,
    summary: str = "",
    reason: str = "ai",
) -> dict:
    """结束场景：effects → scene_logs(finished) → 场景记忆 → 清 active → 解锁 next_scenes。"""
    effects = scene.effects or {}
    attr_changes: list[dict] = []
    if effects.get("attrs"):
        updated, attr_changes = apply_effects(defs_map, values, effects.get("attrs"))
        values.update(updated)
        events.write_changes(session, save.id, values, attr_changes)
    flags = effects.get("flags") or {}
    for key, value in flags.items():
        events.set_flag(session, save.id, str(key), value)
    for key in effects.get("unlock_events") or []:
        events.set_flag(session, save.id, f"event_unlocked:{key}", True)
    for key in effects.get("unlock_scenes") or []:
        events.set_flag(session, save.id, f"scene_unlocked:{key}", True)
    advance = int(_number(effects.get("advance_minutes")) or 0)
    advance = max(0, min(advance, TIME_MAX_JUMP_HOURS * 60))
    turns = int(active.get("turns") or 0)
    summary_text = (summary or "").strip()

    log = _latest_open_log(session, save.id, scene.key)
    if log is None:
        log = SceneLog(
            save_id=save.id,
            scene_key=scene.key,
            status="started",
            game_minutes_at=ctx.absolute,
        )
        session.add(log)
        session.flush()
    log.status = "finished"
    log.summary = summary_text
    log.meta = {
        **(log.meta or {}),
        "name": scene.name,
        "goal": scene.goal or "",
        "reason": reason,
        "turns": turns,
        "attrs": attr_changes,
        "finished_game_minutes": int(save.game_minutes),
    }
    log.finished_at = datetime.now()

    session.add(
        Memory(
            save_id=save.id,
            kind="relationship" if (scene.category or "") == "relationship" else "event",
            content=memory_content(scene, summary_text),
            importance=max(1, min(10, int(SCENE_MEMORY_IMPORTANCE))),
        )
    )

    clear_active(session, save.id)
    events.set_flag(session, save.id, f"scene_done:{scene.key}", True)
    for key in scene.next_scenes or []:
        events.set_flag(session, save.id, f"scene_unlocked:{key}", True)

    end_text = f"【{scene.name}】这一幕结束了。"
    if summary_text:
        end_text += f" {summary_text}"
    message = Message(
        save_id=save.id,
        role="event",
        content=end_text,
        meta={
            "scene_key": scene.key,
            "scene_name": scene.name,
            "kind": "scene_end",
            "reason": reason,
            "log_id": log.id,
        },
        game_minutes_at=ctx.absolute,
    )
    session.add(message)
    session.flush()
    return {
        "key": scene.key,
        "name": scene.name,
        "reason": reason,
        "summary": summary_text,
        "turns": turns,
        "unlocks": list(scene.next_scenes or []),
        "content": end_text,
        "log_id": log.id,
        "message_id": message.id,
        "message": _message_dict(message),
        "attrs": attr_changes,
        "advance_minutes": advance,
    }


def abort_scene(session: Session, save_id: int, scene: SceneDef | None, active: dict) -> dict:
    """强制中止（调试）：清 active 并记 aborted；不应用 effects、不写记忆与收尾消息。"""
    key = str(active.get("key") or "")
    log = _latest_open_log(session, save_id, key) if key else None
    if log is not None:
        log.status = "aborted"
        log.meta = {**(log.meta or {}), "reason": "abort"}
        log.finished_at = datetime.now()
    clear_active(session, save_id)
    return {
        "key": key,
        "name": active.get("name") or (scene.name if scene is not None else key),
        "reason": "abort",
        "turns": int(active.get("turns") or 0),
        "advance_minutes": 0,
    }


def available_scenes(session: Session, save: Save, values: dict[str, float]) -> list[dict]:
    """场景清单（含可用性与禁用原因），供调试进入与前端展示。"""
    scene_defs = list(
        session.scalars(
            select(SceneDef)
            .where(SceneDef.enabled.is_(True))
            .order_by(SceneDef.priority.desc(), SceneDef.id)
        )
    )
    done, last_at = load_scene_stats(session, save.id)
    now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
    ctx = events.build_context(session, save, values)
    items = []
    for scene in scene_defs:
        since = max(0, now_abs - last_at[scene.key]) if scene.key in last_at else None
        ok, reason = scene_availability(
            scene, ctx, triggered=scene.key in done, minutes_since=since
        )
        if ok:
            ok, reason = events.check_cost(values, scene.enter_cost or {})
        items.append({
            "key": scene.key,
            "name": scene.name,
            "category": scene.category,
            "goal": scene.goal or "",
            "enter_cost": scene.enter_cost or {},
            "min_turns": scene.min_turns,
            "max_turns": scene.max_turns,
            "available": ok,
            "reason": reason if not ok else "ok",
        })
    return items


def try_enter(
    session: Session,
    save: Save,
    defs_map,
    values: dict[str, float],
    *,
    source: str = "auto",
    forced_key: str | None = None,
) -> dict | None:
    """无活跃场景时评估进入条件；forced_key（事件 effects.start_scene）优先。"""
    scene_defs = list(
        session.scalars(
            select(SceneDef)
            .where(SceneDef.enabled.is_(True))
            .order_by(SceneDef.priority.desc(), SceneDef.id)
        )
    )
    if not scene_defs:
        return None
    if forced_key:
        scene_defs = [s for s in scene_defs if s.key == forced_key]
    if not scene_defs:
        return None
    done, last_at = load_scene_stats(session, save.id)
    now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
    ctx = events.build_context(session, save, values)
    rng = random.Random()
    for scene in scene_defs:
        since = max(0, now_abs - last_at[scene.key]) if scene.key in last_at else None
        ok, _reason = scene_availability(
            scene,
            ctx,
            triggered=scene.key in done,
            minutes_since=since,
            rng=rng,
            allow_chance=True,
        )
        if not ok:
            continue
        ok, _reason = events.check_cost(values, scene.enter_cost or {})
        if not ok:
            continue
        return enter_scene(session, save, scene, ctx, values, defs_map, source=source)
    return None


def settle_scenes(
    session: Session,
    save: Save,
    defs_map,
    values: dict[str, float],
    *,
    source: str = "chat",
    state_scene: dict | None = None,
    forced_key: str | None = None,
    skip_enter: bool = False,
) -> dict:
    """场景生命周期统一结算：先结束判定（进行中），再进入评估（无活跃场景时）。

    source="chat" 视为一轮对话（turns +1）；state_scene 为 AI 状态标签中的 scene 动作。
    skip_enter 用于「本幕刚结束」的调用方，本次结算不再接力进入新场景。
    返回 {entered, ended, active}；调用方负责 commit 与推进时间。
    """
    active = get_active(session, save.id)
    entered = ended = None
    if active:
        scene = session.scalar(
            select(SceneDef).where(SceneDef.key == str(active.get("key") or ""))
        )
        if scene is None or not scene.enabled:
            clear_active(session, save.id)
            active = None
    if active:
        is_turn = source == "chat"
        turns_after = int(active.get("turns") or 0) + (1 if is_turn else 0)
        ai_end = False
        ai_summary = ""
        if is_turn and isinstance(state_scene, dict):
            if str(state_scene.get("action") or "").strip().lower() == "end":
                ai_end = True
                ai_summary = str(state_scene.get("summary") or "").strip()
        ctx = events.build_context(session, save, values)
        exit_met = bool(scene.exit) and events.evaluate(
            scene.exit, ctx, rng=random.Random(), allow_chance=True
        )
        reason = should_finish(scene, turns_after, ai_end=ai_end, exit_met=exit_met)
        if reason:
            ended = finish_scene(
                session,
                save,
                scene,
                {**active, "turns": turns_after},
                ctx,
                values,
                defs_map,
                summary=ai_summary,
                reason=reason,
            )
            active = None
        elif is_turn:
            active = {**active, "turns": turns_after}
            set_active(session, save.id, active)
    if active is None and ended is None and not skip_enter:
        entered = try_enter(
            session, save, defs_map, values, source=source, forced_key=forced_key
        )
        if entered:
            active = get_active(session, save.id)
    return {"entered": entered, "ended": ended, "active": active}
