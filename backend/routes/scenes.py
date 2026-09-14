"""
场景接口 — 场景历史、手动进入（调试）与手动结束（PLAN 5.3 / 第 7 节）。

进入/结束均走场景引擎与统一结算（save 级串行锁），与对话流后结算同口径。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_session
from game import clock, events, scenes
from helpers import error, get_save_or_error, load_attr_values, save_settle_lock
from orm import AttributeDef, SceneDef, SceneLog
from schemas import SceneEndIn, SceneEnterIn

router = APIRouter(tags=["scenes"])


def _virtual(save) -> dict:
    abs_now = clock.absolute_minutes(save.game_minutes, save.settings or {})
    return {
        "absolute_minutes": abs_now,
        **clock.split(abs_now),
        "label": clock.time_label(abs_now),
    }


@router.get("/api/saves/{save_id}/scenes")
def list_scenes(
    save_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    save = get_save_or_error(session, save_id)
    active = scenes.get_active(session, save_id)
    rows = session.scalars(
        select(SceneLog)
        .where(SceneLog.save_id == save_id)
        .order_by(SceneLog.id.desc())
        .limit(limit)
    ).all()
    values = load_attr_values(session, save_id)
    items = []
    for log in rows:
        meta = log.meta or {}
        abs_at = int(log.game_minutes_at or 0)
        items.append({
            "id": log.id,
            "scene_key": log.scene_key,
            "name": meta.get("name") or log.scene_key,
            "status": log.status,
            "summary": log.summary,
            "reason": meta.get("reason", ""),
            "turns": meta.get("turns", 0),
            "game_minutes_at": abs_at,
            "virtual_label": clock.time_label(abs_at),
            "started_at": log.started_at,
            "finished_at": log.finished_at,
        })
    return {
        "active": scenes.public_active(active),
        "scenes": items,
        "available": scenes.available_scenes(session, save, values),
    }


@router.post("/api/saves/{save_id}/scenes")
def enter_scene(
    save_id: int, req: SceneEnterIn, session: Session = Depends(get_session)
):
    with save_settle_lock(save_id):
        save = get_save_or_error(session, save_id)
        if scenes.get_active(session, save_id):
            error("scene_busy", "已有进行中的场景，请先结束它", 409)
        scene = session.scalar(select(SceneDef).where(SceneDef.key == req.key))
        if scene is None:
            error("scene_not_found", f"场景不存在：{req.key}", 404)

        defs = list(session.scalars(select(AttributeDef)))
        defs_map = {d.key: d for d in defs}
        values = load_attr_values(session, save_id)
        done, last_at = scenes.load_scene_stats(session, save_id)
        now_abs = clock.absolute_minutes(save.game_minutes, save.settings or {})
        since = max(0, now_abs - last_at[scene.key]) if scene.key in last_at else None
        ctx = events.build_context(session, save, values)
        ok, reason = scenes.scene_availability(
            scene, ctx, triggered=scene.key in done, minutes_since=since
        )
        if not ok:
            error(
                "scene_locked",
                events.MANUAL_REASON_TEXT.get(reason, "当前不可用"),
                409,
            )
        ok, _reason = events.check_cost(values, scene.enter_cost or {})
        if not ok:
            error("insufficient_money", "金钱不足，无法承担这项花费", 400)

        old_game = int(save.game_minutes)
        entered = scenes.enter_scene(
            session, save, scene, ctx, values, defs_map, source="manual"
        )
        settled = events.settle_time(
            session,
            save,
            defs,
            values,
            save.game_minutes + entered["advance_minutes"],
            source="manual",
        )
        session.commit()
        return {
            "scene": scenes.brief(entered),
            "active": scenes.public_active(scenes.get_active(session, save_id)),
            "game_minutes": save.game_minutes,
            "advance_minutes": int(save.game_minutes) - old_game,
            "virtual": _virtual(save),
            "changes": entered["attrs"] + settled["tick_changes"],
            "messages": [entered["message"], *settled["messages"]],
        }


@router.post("/api/saves/{save_id}/scenes/end")
def end_scene(
    save_id: int, req: SceneEndIn, session: Session = Depends(get_session)
):
    with save_settle_lock(save_id):
        save = get_save_or_error(session, save_id)
        active = scenes.get_active(session, save_id)
        if active is None:
            error("no_active_scene", "当前没有进行中的场景", 404)
        scene = session.scalar(
            select(SceneDef).where(SceneDef.key == str(active.get("key") or ""))
        )
        if req.abort:
            aborted = scenes.abort_scene(session, save_id, scene, active)
            session.commit()
            return {
                "scene": scenes.brief(aborted),
                "active": None,
                "game_minutes": save.game_minutes,
                "advance_minutes": 0,
                "virtual": _virtual(save),
                "changes": [],
                "messages": [],
            }
        if scene is None:
            scenes.clear_active(session, save_id)
            session.commit()
            error("scene_not_found", "场景定义不存在，已清除进行中的场景", 404)

        defs = list(session.scalars(select(AttributeDef)))
        defs_map = {d.key: d for d in defs}
        values = load_attr_values(session, save_id)
        ctx = events.build_context(session, save, values)
        old_game = int(save.game_minutes)
        ended = scenes.finish_scene(
            session,
            save,
            scene,
            active,
            ctx,
            values,
            defs_map,
            summary=req.summary,
            reason="manual",
        )
        settled = events.settle_time(
            session,
            save,
            defs,
            values,
            save.game_minutes + ended["advance_minutes"],
            source="manual",
        )
        session.commit()
        return {
            "scene": scenes.brief(ended),
            "active": None,
            "game_minutes": save.game_minutes,
            "advance_minutes": int(save.game_minutes) - old_game,
            "virtual": _virtual(save),
            "changes": ended["attrs"] + settled["tick_changes"],
            "messages": [ended["message"], *settled["messages"]],
        }
