"""
永久记忆接口 — 列表/新增/编辑/归档/删除与手动总结（PLAN 5.6 / 第 7 节）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from db import SessionLocal, get_session
from game import memory
from game.memory import KINDS
from helpers import error, get_save_or_error
from orm import Memory, MemoryJob
from schemas import MemoryIn, MemoryPatch

router = APIRouter(tags=["memories"])

STATUSES = ("active", "archived")


def _memory_dict(row: Memory) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "content": row.content,
        "importance": row.importance,
        "status": row.status,
        "recall_count": row.recall_count,
        "created_at": row.created_at,
        "last_recalled_at": row.last_recalled_at,
    }


def _job_dict(job: MemoryJob | None) -> dict | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at,
    }


@router.get("/api/saves/{save_id}/memories")
def list_memories(
    save_id: int,
    status: str | None = Query(default=None, max_length=16),
    session: Session = Depends(get_session),
):
    get_save_or_error(session, save_id)
    query = select(Memory).where(Memory.save_id == save_id)
    if status in STATUSES:
        query = query.where(Memory.status == status)
    rows = session.scalars(
        query.order_by(Memory.importance.desc(), Memory.id.desc())
    ).all()
    job = session.scalar(
        select(MemoryJob)
        .where(MemoryJob.save_id == save_id)
        .order_by(MemoryJob.id.desc())
        .limit(1)
    )
    return {
        "memories": [_memory_dict(r) for r in rows],
        "unsummarized": memory.count_unsummarized(session, save_id),
        "job": _job_dict(job),
    }


@router.post("/api/saves/{save_id}/memories")
def create_memory(
    save_id: int, req: MemoryIn, session: Session = Depends(get_session)
):
    get_save_or_error(session, save_id)
    kind = req.kind.strip().lower()
    if kind not in KINDS:
        error("invalid_kind", f"kind 只能是 {'/'.join(KINDS)}", 400)
    content = req.content.strip()
    if not content:
        error("invalid_content", "记忆内容不能为空", 400)
    row = Memory(
        save_id=save_id, kind=kind, content=content, importance=req.importance
    )
    session.add(row)
    session.commit()
    return _memory_dict(row)


@router.patch("/api/saves/{save_id}/memories/{memory_id}")
def update_memory(
    save_id: int,
    memory_id: int,
    req: MemoryPatch,
    session: Session = Depends(get_session),
):
    get_save_or_error(session, save_id)
    row = session.get(Memory, memory_id)
    if row is None or row.save_id != save_id:
        error("memory_not_found", "记忆不存在", 404)
    if req.kind is not None:
        kind = req.kind.strip().lower()
        if kind not in KINDS:
            error("invalid_kind", f"kind 只能是 {'/'.join(KINDS)}", 400)
        row.kind = kind
    if req.content is not None:
        content = req.content.strip()
        if not content:
            error("invalid_content", "记忆内容不能为空", 400)
        row.content = content
    if req.importance is not None:
        row.importance = req.importance
    if req.status is not None:
        status = req.status.strip().lower()
        if status not in STATUSES:
            error("invalid_status", "状态只能是 active / archived", 400)
        row.status = status
    session.commit()
    return _memory_dict(row)


@router.delete("/api/saves/{save_id}/memories/{memory_id}")
def delete_memory(
    save_id: int, memory_id: int, session: Session = Depends(get_session)
):
    get_save_or_error(session, save_id)
    row = session.get(Memory, memory_id)
    if row is None or row.save_id != save_id:
        error("memory_not_found", "记忆不存在", 404)
    session.delete(row)
    session.commit()
    return {"ok": True}


def _ensure_save(save_id: int) -> None:
    session = SessionLocal()
    try:
        get_save_or_error(session, save_id)
    finally:
        session.close()


def _latest_job(save_id: int) -> dict | None:
    session = SessionLocal()
    try:
        job = session.scalar(
            select(MemoryJob)
            .where(MemoryJob.save_id == save_id)
            .order_by(MemoryJob.id.desc())
            .limit(1)
        )
        return _job_dict(job)
    finally:
        session.close()


@router.post("/api/saves/{save_id}/memories/summarize")
async def summarize(save_id: int):
    """手动触发一次总结（同步等待结果，供记忆面板使用）。"""
    await run_in_threadpool(_ensure_save, save_id)
    result = await memory.run_summary(save_id)
    if result is None:
        job = await run_in_threadpool(_latest_job, save_id)
        status = (job or {}).get("status")
        if status == "running":
            message = "已有一次总结正在进行，请稍后再试"
        elif status == "failed":
            message = f"总结失败：{(job or {}).get('error') or '未知原因'}"
        else:
            message = "没有需要总结的新内容"
        return {
            "added": [],
            "skipped": 0,
            "extracted": 0,
            "job": job,
            "message": message,
        }
    return {
        **result,
        "job": await run_in_threadpool(_latest_job, save_id),
        "message": (
            f"总结完成：新增 {len(result['added'])} 条，去重跳过 {result['skipped']} 条"
        ),
    }
