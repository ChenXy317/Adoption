"""
SSE 对话 — 流式生成、状态标签剥离与落库结算（PLAN 5.5）。

流式阶段不做 DB 写；DB 访问集中在流前（组装上下文）与流后（结算落库）两端。
流后结算顺序：AI 属性/时间 → tick → 跨日随机判定 → 事件触发，同一事务提交。
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ai_client import AIClientError, ai
from config import CHAT_HISTORY_MESSAGES, EVENT_RECENT_WINDOW_MINUTES
from db import SessionLocal
from game import clock, events, memory, scenes
from game.attributes import apply_deltas, phase_of
from game.prompt import build_messages
from game.tags import StateTagStripper, parse_state
from helpers import get_runtime, get_save_or_error, load_attr_values, save_settle_lock
from orm import AttributeDef, Character, Message, Save
from schemas import ChatIn

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class SaveGoneError(Exception):
    """结算时存档已被删除。"""


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _prepare(save_id: int, message: str) -> dict:
    """流前：落用户消息 + 组装 prompt（含当前事件情境）。"""
    session = SessionLocal()
    try:
        save = get_save_or_error(session, save_id)
        if not save.model_key:
            from helpers import error

            error("model_not_set", "该存档尚未选择模型，请先在「模型配置」中选择", 400)
        runtime = get_runtime(session, save.model_key)
        character = (
            session.get(Character, save.character_id) if save.character_id else None
        )
        if character is None:
            from helpers import error

            error("character_missing", "该存档未关联女主角设定书", 400)
        settings = save.settings or {}
        abs_now = clock.absolute_minutes(save.game_minutes, settings)
        user_msg = Message(
            save_id=save_id,
            role="user",
            content=message,
            game_minutes_at=abs_now,
        )
        session.add(user_msg)
        session.commit()

        history = list(
            session.scalars(
                select(Message)
                .where(Message.save_id == save_id)
                .order_by(Message.id.desc())
                .limit(CHAT_HISTORY_MESSAGES)
            )
        )
        history.reverse()
        defs = list(
            session.scalars(
                select(AttributeDef).order_by(AttributeDef.sort, AttributeDef.id)
            )
        )
        values = load_attr_values(session, save_id)
        active_events = events.recent_events(
            session, save, window_minutes=EVENT_RECENT_WINDOW_MINUTES, limit=3
        )
        active_scene = scenes.get_active(session, save_id)
        memories = memory.retrieve(session, save_id)
        if memories:
            memory.mark_recalled(session, [m["id"] for m in memories])
            session.commit()
        messages = build_messages(
            save,
            character,
            defs,
            values,
            history,
            settings,
            active_events,
            active_scene,
            memories,
        )
        return {
            "messages": messages,
            "model_id": runtime["model_id"],
            "base_url": runtime["base_url"],
            "api_key": runtime["api_key"],
            "max_tokens": runtime["max_tokens"],
            "params": settings.get("params") or {},
            "user_message_id": user_msg.id,
        }
    finally:
        session.close()


def _settle(save_id: int, text: str, tag_raw: str, interrupted: bool) -> dict:
    """流后：解析状态标签 → 应用属性/时间 → 事件结算 → 同一事务落库。"""
    session = SessionLocal()
    try:
        with save_settle_lock(save_id):
            save = session.get(Save, save_id)
            if save is None:
                raise SaveGoneError(f"存档 {save_id} 已被删除")
            settings = save.settings or {}
            default_advance, max_advance = clock.advance_limits(settings)
            defs = list(session.scalars(select(AttributeDef)))
            defs_map = {d.key: d for d in defs}
            values = load_attr_values(session, save_id)
            old_game = int(save.game_minutes)
            state = parse_state(tag_raw)
            changes: list[dict] = []
            raw_advance = None
            raw_scene = None
            if state is not None:
                raw_attrs = state.get("attrs")
                updated, changes = apply_deltas(
                    defs_map, values, raw_attrs if isinstance(raw_attrs, dict) else {}
                )
                values.update(updated)
                events.write_changes(session, save_id, values, changes)
                raw_time = state.get("time")
                if isinstance(raw_time, dict):
                    raw_advance = raw_time.get("advance_minutes")
                if isinstance(state.get("scene"), dict):
                    raw_scene = state.get("scene")
            if raw_advance is None:
                time_advance = default_advance
            else:
                try:
                    time_advance = int(raw_advance)
                except (TypeError, ValueError):
                    time_advance = default_advance
            time_advance = max(0, min(int(time_advance), max_advance))

            abs_before = clock.absolute_minutes(old_game, settings)
            meta: dict = {"attrs": changes, "time_advance": time_advance}
            if interrupted:
                meta["interrupted"] = True
            if state is None:
                meta["state_parse_failed"] = True
                meta["tag_debug"] = (tag_raw or text[-500:])[:1000]
            assistant = None
            if text.strip():
                assistant = Message(
                    save_id=save_id,
                    role="assistant",
                    content=text,
                    meta=meta,
                    game_minutes_at=abs_before,
                )
                session.add(assistant)
                session.flush()

            settled = events.settle_time(
                session,
                save,
                defs,
                values,
                old_game + time_advance,
                source="chat",
                state_scene=raw_scene,
            )
            total_advance = int(save.game_minutes) - old_game
            meta["ticks"] = settled["tick_changes"]
            if settled["triggered"]:
                meta["events"] = [item["key"] for item in settled["triggered"]]
            scene_info = settled.get("scene") or {}
            if scene_info.get("entered"):
                meta["scene_entered"] = scene_info["entered"]["key"]
            if scene_info.get("ended"):
                meta["scene_ended"] = scene_info["ended"]["key"]
            if assistant is not None:
                assistant.game_minutes_at = settled["absolute_minutes"]
            session.commit()
            memory_due = memory.trigger_if_due(session, save_id)

            abs_minutes = clock.absolute_minutes(save.game_minutes, settings)
            virtual = {
                "absolute_minutes": abs_minutes,
                **clock.split(abs_minutes),
                "label": clock.time_label(abs_minutes),
            }
            combined = (
                changes
                + settled["tick_changes"]
                + [c for item in settled["triggered"] for c in item["attrs"]]
            )
            return {
                "message_id": assistant.id if assistant else None,
                "changes": combined,
                "ai_changes": changes,
                "phase": phase_of(values),
                "time_advance": total_advance,
                "game_minutes": save.game_minutes,
                "virtual": virtual,
                "parsed": state is not None,
                "interrupted": interrupted,
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
                "scene": {
                    "entered": scenes.brief(scene_info.get("entered")),
                    "ended": scenes.brief(scene_info.get("ended")),
                    "active": scene_info.get("active"),
                },
                "memory_due": memory_due,
                "messages": settled["messages"],
            }
    finally:
        session.close()


def _settle_in_thread(save_id: int, text: str, tag_raw: str) -> None:
    """客户端断开时的兜底结算（不阻塞事件循环）。"""

    def run():
        try:
            _settle(save_id, text, tag_raw, True)
        except Exception:
            logger.exception("中断回复的兜底结算失败")

    threading.Thread(target=run, daemon=True).start()


@router.post("/api/saves/{save_id}/chat")
async def chat(save_id: int, req: ChatIn, background: BackgroundTasks):
    message = req.message.strip()
    prepared = await run_in_threadpool(_prepare, save_id, message)

    async def event_gen():
        stripper = StateTagStripper()
        collected: list[str] = []
        error_payload = None
        try:
            try:
                async for text in ai.stream_chat(
                    messages=prepared["messages"],
                    model_id=prepared["model_id"],
                    base_url=prepared["base_url"],
                    api_key=prepared["api_key"],
                    max_tokens=prepared["max_tokens"],
                    params=prepared["params"],
                ):
                    visible = stripper.feed(text)
                    if visible:
                        collected.append(visible)
                        yield sse("chunk", {"text": visible})
            except AIClientError as e:
                error_payload = {"code": e.error_code, "message": str(e)}
        except (asyncio.CancelledError, GeneratorExit):
            if collected or stripper.tag_found:
                _settle_in_thread(save_id, "".join(collected), stripper.state_raw)
            raise

        tail = stripper.flush()
        if tail:
            collected.append(tail)
            yield sse("chunk", {"text": tail})

        text = "".join(collected)
        if not text and not stripper.tag_found:
            yield sse(
                "error",
                error_payload
                or {"code": "empty_reply", "message": "模型没有返回任何内容"},
            )
            return
        settled = None
        try:
            settled = await run_in_threadpool(
                _settle, save_id, text, stripper.state_raw, error_payload is not None
            )
        except SaveGoneError:
            yield sse(
                "error",
                {"code": "save_not_found", "message": "存档不存在或已被删除"},
            )
            return
        if settled["changes"]:
            yield sse(
                "state_update",
                {
                    "attrs": settled["changes"],
                    "phase": settled["phase"],
                    "game_minutes": settled["game_minutes"],
                    "virtual_label": settled["virtual"]["label"],
                },
            )
        if settled["events"] or settled["messages"]:
            yield sse(
                "event_triggered",
                {
                    "events": settled["events"],
                    "messages": settled["messages"],
                },
            )
        if settled["scene"]["entered"] or settled["scene"]["ended"]:
            yield sse(
                "scene_update",
                {
                    "entered": settled["scene"]["entered"],
                    "ended": settled["scene"]["ended"],
                    "active": settled["scene"]["active"],
                },
            )
        yield sse(
            "time_update",
            {
                "advance_minutes": settled["time_advance"],
                "game_minutes": settled["game_minutes"],
                "virtual_label": settled["virtual"]["label"],
                "virtual": settled["virtual"],
            },
        )
        if settled.get("memory_due"):
            background.add_task(memory.safe_run_summary, save_id)
        if error_payload is not None:
            yield sse("error", error_payload)
        else:
            yield sse(
                "done",
                {
                    "message_id": settled["message_id"],
                    "meta": {
                        "attrs": settled["ai_changes"],
                        "time_advance": settled["time_advance"],
                    },
                    "game_minutes": settled["game_minutes"],
                    "virtual_label": settled["virtual"]["label"],
                },
            )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
        background=background,
    )
