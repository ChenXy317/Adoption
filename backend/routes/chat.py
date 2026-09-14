"""
SSE 对话 — 流式生成、状态标签剥离与落库结算（PLAN 5.5）。

流式阶段不做 DB 写；DB 访问集中在流前（组装上下文）与流后（结算落库）两端。
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ai_client import AIClientError, ai
from config import CHAT_HISTORY_MESSAGES, TIME_DEFAULT_ADVANCE, TIME_MAX_ADVANCE_PER_MESSAGE
from db import SessionLocal
from game import clock
from game.attributes import apply_deltas, phase_of
from game.prompt import build_messages
from game.tags import StateTagStripper, parse_state
from helpers import get_runtime, get_save_or_error, load_attr_values
from orm import AttributeDef, AttributeValue, Character, Message, Save
from schemas import ChatIn

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _prepare(save_id: int, message: str) -> dict:
    """流前：落用户消息 + 组装 prompt。"""
    session = SessionLocal()
    try:
        save = get_save_or_error(session, save_id)
        if not save.model_key:
            from helpers import error

            error("model_not_set", "该存档尚未选择模型，请先在「模型配置」中选择", 400)
        runtime = get_runtime(session, save.model_key)
        character = (
            session.get(Character, save.character_id)
            if save.character_id
            else None
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
        messages = build_messages(save, character, defs, values, history, settings)
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
    """流后：解析状态标签 → 应用属性/时间 → 同一事务落 assistant 消息。"""
    session = SessionLocal()
    try:
        save = session.get(Save, save_id)
        settings = save.settings or {}
        defs = {d.key: d for d in session.scalars(select(AttributeDef))}
        values = load_attr_values(session, save_id)
        state = parse_state(tag_raw)
        changes: list[dict] = []
        phase_label: str | None = None
        time_advance = 0
        if state is not None:
            new_values, changes = apply_deltas(
                defs, values, state.get("attrs") or {}
            )
            phase_label = phase_of(new_values)
            for key, value in new_values.items():
                if values.get(key) == value:
                    continue
                row = session.get(AttributeValue, (save_id, key))
                if row is not None:
                    row.value = value
            time_part = state.get("time") or {}
            raw_advance = time_part.get("advance_minutes")
            if raw_advance is None:
                time_advance = TIME_DEFAULT_ADVANCE
            else:
                try:
                    time_advance = int(raw_advance)
                except (TypeError, ValueError):
                    time_advance = TIME_DEFAULT_ADVANCE
        else:
            time_advance = TIME_DEFAULT_ADVANCE
        time_advance = max(0, min(int(time_advance), TIME_MAX_ADVANCE_PER_MESSAGE))
        save.game_minutes += time_advance

        abs_minutes = clock.absolute_minutes(save.game_minutes, settings)
        virtual = {
            "absolute_minutes": abs_minutes,
            **clock.split(abs_minutes),
            "label": clock.time_label(abs_minutes),
        }

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
                game_minutes_at=abs_minutes,
            )
            session.add(assistant)
        session.commit()
        return {
            "message_id": assistant.id if assistant else None,
            "changes": changes,
            "phase": phase_label,
            "time_advance": time_advance,
            "game_minutes": save.game_minutes,
            "virtual": virtual,
            "parsed": state is not None,
            "interrupted": interrupted,
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
async def chat(save_id: int, req: ChatIn):
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
        settled = await run_in_threadpool(
            _settle, save_id, text, stripper.state_raw, error_payload is not None
        )
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
        yield sse(
            "time_update",
            {
                "advance_minutes": settled["time_advance"],
                "game_minutes": settled["game_minutes"],
                "virtual_label": settled["virtual"]["label"],
                "virtual": settled["virtual"],
            },
        )
        if error_payload is not None:
            yield sse("error", error_payload)
        else:
            yield sse(
                "done",
                {
                    "message_id": settled["message_id"],
                    "meta": {
                        "attrs": settled["changes"],
                        "time_advance": settled["time_advance"],
                    },
                    "game_minutes": settled["game_minutes"],
                    "virtual_label": settled["virtual"]["label"],
                },
            )

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=SSE_HEADERS)
