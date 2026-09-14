"""
备份与恢复 — 存档全量导出与导入（M6，PLAN §9）。

导出为单个 JSON 文件（存档元数据、属性、标记、消息、事件/场景日志、记忆与角色快照）；
导入时创建为新存档并重建消息 id 映射，不改动全局女主角与事件/场景定义。
"""
from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_client import AIClientError
from db import get_session
from game import events, memory
from helpers import error, get_global_character, get_runtime, get_save_or_error
from orm import (
    AttributeValue,
    Character,
    EventDef,
    EventLog,
    Memory,
    Message,
    Save,
    SaveFlag,
    SceneLog,
)
from routes.saves import save_summary

router = APIRouter(tags=["backup"])

BACKUP_FORMAT = "new-idea-save"
BACKUP_VERSION = 1

MAX_NAME_LENGTH = 128
MAX_IMPORT_MESSAGES = 50000

_ROLES = ("user", "assistant", "system", "event")
_MEMORY_STATUSES = ("active", "archived")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_backup(session: Session, save: Save) -> dict:
    """组装存档的完整导出结构。"""
    character = (
        session.get(Character, save.character_id) if save.character_id else None
    )
    attributes = [
        {"key": row.attr_key, "value": row.value}
        for row in session.scalars(
            select(AttributeValue)
            .where(AttributeValue.save_id == save.id)
            .order_by(AttributeValue.attr_key)
        )
    ]
    flag_map = events.load_flags(session, save.id)
    flags = [
        {"key": key, "value": flag_map[key]} for key in sorted(flag_map.keys())
    ]
    messages = [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "meta": row.meta or {},
            "game_minutes_at": row.game_minutes_at,
            "created_at": _iso(row.created_at),
        }
        for row in session.scalars(
            select(Message).where(Message.save_id == save.id).order_by(Message.id)
        )
    ]
    event_rows = session.execute(
        select(EventLog, EventDef.key)
        .outerjoin(EventDef, EventLog.event_id == EventDef.id)
        .where(EventLog.save_id == save.id)
        .order_by(EventLog.id)
    ).all()
    event_logs = []
    for log, def_key in event_rows:
        meta = log.meta or {}
        event_logs.append({
            "event_key": str(meta.get("key") or def_key or ""),
            "status": log.status,
            "content": log.content,
            "meta": meta,
            "game_minutes_at": log.game_minutes_at,
            "triggered_at": _iso(log.triggered_at),
        })
    scene_logs = [
        {
            "scene_key": row.scene_key,
            "status": row.status,
            "summary": row.summary,
            "meta": row.meta or {},
            "game_minutes_at": row.game_minutes_at,
            "started_at": _iso(row.started_at),
            "finished_at": _iso(row.finished_at),
        }
        for row in session.scalars(
            select(SceneLog).where(SceneLog.save_id == save.id).order_by(SceneLog.id)
        )
    ]
    memories = [
        {
            "kind": row.kind,
            "content": row.content,
            "importance": row.importance,
            "source_from_id": row.source_from_id,
            "source_to_id": row.source_to_id,
            "status": row.status,
            "recall_count": row.recall_count,
            "last_recalled_at": _iso(row.last_recalled_at),
            "created_at": _iso(row.created_at),
        }
        for row in session.scalars(
            select(Memory).where(Memory.save_id == save.id).order_by(Memory.id)
        )
    ]
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": datetime.now().isoformat(),
        "save": {
            "name": save.name,
            "model_key": save.model_key,
            "game_minutes": save.game_minutes,
            "last_summarized_message_id": save.last_summarized_message_id,
            "settings": save.settings or {},
            "created_at": _iso(save.created_at),
            "updated_at": _iso(save.updated_at),
        },
        "character": (
            {
                "name": character.name,
                "age": character.age,
                "relation": character.relation,
                "persona": character.persona or {},
                "freeform": character.freeform or "",
            }
            if character
            else None
        ),
        "attributes": attributes,
        "flags": flags,
        "messages": messages,
        "event_logs": event_logs,
        "scene_logs": scene_logs,
        "memories": memories,
    }


def import_backup(session: Session, payload: dict, name: str | None = None) -> Save:
    """把导出结构导入为新存档（同一事务内完成）。"""
    if not isinstance(payload, dict) or payload.get("format") != BACKUP_FORMAT:
        error("invalid_backup", "备份文件格式不正确", 400)
    if _as_int(payload.get("version")) != BACKUP_VERSION:
        error(
            "unsupported_version",
            f"暂不支持的备份版本：{payload.get('version')}",
            400,
        )
    character = get_global_character(session)
    if character is None:
        error("character_required", "还没有女主角设定书，无法导入存档", 400)

    raw = payload.get("save")
    raw = raw if isinstance(raw, dict) else {}
    raw_name = str(raw.get("name") or "").strip()
    target_name = (name or "").strip() or f"{raw_name or '未命名存档'}（恢复）"
    target_name = target_name[:MAX_NAME_LENGTH]

    model_key = str(raw.get("model_key") or "").strip()
    if model_key:
        try:
            get_runtime(session, model_key, http=False)
        except AIClientError:
            model_key = ""

    save = Save(
        character_id=character.id,
        name=target_name,
        model_key=model_key,
        game_minutes=max(0, _as_int(raw.get("game_minutes"))),
        last_summarized_message_id=0,
        settings=raw.get("settings") if isinstance(raw.get("settings"), dict) else {},
    )
    session.add(save)
    session.flush()

    for item in payload.get("attributes") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        session.add(
            AttributeValue(
                save_id=save.id,
                attr_key=key[:64],
                value=_as_float(item.get("value")),
            )
        )

    for item in payload.get("flags") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        events.set_flag(session, save.id, key[:64], item.get("value"))

    raw_messages = [x for x in (payload.get("messages") or []) if isinstance(x, dict)]
    if len(raw_messages) > MAX_IMPORT_MESSAGES:
        error(
            "backup_too_large",
            f"备份消息数量超出上限（{MAX_IMPORT_MESSAGES} 条）",
            400,
        )
    id_map: dict[int, int] = {}
    message_rows: list[Message] = []
    for item in raw_messages:
        role = str(item.get("role") or "user").strip().lower()
        if role not in _ROLES:
            role = "system"
        message_rows.append(
            Message(
                save_id=save.id,
                role=role,
                content=str(item.get("content") or ""),
                meta=item.get("meta") if isinstance(item.get("meta"), dict) else {},
                game_minutes_at=_as_int(item.get("game_minutes_at")),
                created_at=_parse_dt(item.get("created_at")) or datetime.now(),
            )
        )
    session.add_all(message_rows)
    session.flush()
    for item, row in zip(raw_messages, message_rows):
        old_id = _as_int(item.get("id"))
        if old_id > 0:
            id_map[old_id] = row.id

    event_ids = {row.key: row.id for row in session.scalars(select(EventDef))}
    for item in payload.get("event_logs") or []:
        if not isinstance(item, dict):
            continue
        event_key = str(item.get("event_key") or "").strip()
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        if event_key and "key" not in meta:
            meta = {**meta, "key": event_key}
        session.add(
            EventLog(
                save_id=save.id,
                event_id=event_ids.get(event_key),
                status=str(item.get("status") or "triggered")[:16],
                content=str(item.get("content") or ""),
                meta=meta,
                game_minutes_at=_as_int(item.get("game_minutes_at")),
                triggered_at=_parse_dt(item.get("triggered_at")) or datetime.now(),
            )
        )

    for item in payload.get("scene_logs") or []:
        if not isinstance(item, dict):
            continue
        scene_key = str(item.get("scene_key") or "").strip()
        if not scene_key:
            continue
        session.add(
            SceneLog(
                save_id=save.id,
                scene_key=scene_key[:64],
                status=str(item.get("status") or "started")[:16],
                summary=str(item.get("summary") or ""),
                meta=item.get("meta") if isinstance(item.get("meta"), dict) else {},
                game_minutes_at=_as_int(item.get("game_minutes_at")),
                started_at=_parse_dt(item.get("started_at")) or datetime.now(),
                finished_at=_parse_dt(item.get("finished_at")),
            )
        )

    for item in payload.get("memories") or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        kind = str(item.get("kind") or "fact").strip().lower()
        if kind not in memory.KINDS:
            kind = "fact"
        status = str(item.get("status") or "active").strip().lower()
        if status not in _MEMORY_STATUSES:
            status = "active"
        importance = max(1, min(10, _as_int(item.get("importance"), 5)))
        source_from = _as_int(item.get("source_from_id"))
        source_to = _as_int(item.get("source_to_id"))
        session.add(
            Memory(
                save_id=save.id,
                kind=kind,
                content=content,
                importance=importance,
                source_from_id=id_map.get(source_from) if source_from else None,
                source_to_id=id_map.get(source_to) if source_to else None,
                status=status,
                recall_count=max(0, _as_int(item.get("recall_count"))),
                last_recalled_at=_parse_dt(item.get("last_recalled_at")),
                created_at=_parse_dt(item.get("created_at")) or datetime.now(),
            )
        )

    old_last = _as_int(raw.get("last_summarized_message_id"))
    if old_last > 0 and id_map:
        candidates = [new for old, new in id_map.items() if old <= old_last]
        if candidates:
            save.last_summarized_message_id = max(candidates)

    session.commit()
    return save


@router.get("/api/saves/{save_id}/export")
def export_save(save_id: int, session: Session = Depends(get_session)):
    """导出存档全量备份（JSON 文件下载）。"""
    save = get_save_or_error(session, save_id)
    payload = build_backup(session, save)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    safe_name = save.name.replace("/", "_").replace("\\", "_").strip() or "存档"
    filename = f"养成存档-{safe_name}-{datetime.now():%Y%m%d%H%M}.json"
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.post("/api/saves/import")
def import_save(
    payload: dict = Body(...),
    name: str | None = Query(default=None, max_length=MAX_NAME_LENGTH),
    session: Session = Depends(get_session),
):
    """导入备份文件为新存档（不动现有存档）。"""
    save = import_backup(session, payload, name=name)
    return save_summary(session, save)
