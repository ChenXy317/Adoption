"""
记忆系统 — 永久记忆的总结流水线、检索与注入（PLAN 5.6）。

- 纯函数区：parse_summary / merge_entries / memory_score / select_memories / 时间线组装
- DB 区：总结 job 的触发与抢占（save 级互斥）、总结任务的准备与落库、检索与召回标记

总结由「未总结消息 ≥ 阈值 / 手动 / 启动补跑」触发，LLM 结构化抽取条目
（kind=fact/event/relationship/promise），去重合并后写 memories 并推进
last_summarized_message_id；失败与中断记 memory_jobs 留待下次重试。
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai_client import AIClientError, ai
from config import (
    MEMORY_CHAR_BUDGET,
    MEMORY_EXISTING_LIMIT,
    MEMORY_MAX_MESSAGES_PER_JOB,
    MEMORY_MODEL,
    MEMORY_PROMPT_CHAR_BUDGET,
    MEMORY_SUMMARY_MAX_TOKENS,
    MEMORY_TRIGGER_TURNS,
)
from db import SessionLocal
from helpers import get_runtime, save_settle_lock
from orm import EventLog, Memory, MemoryJob, Message, Save

logger = logging.getLogger(__name__)

KINDS = ("fact", "event", "relationship", "promise")
CORE_IMPORTANCE = 8
_MAX_CONTENT_CHARS = 300

SUMMARY_SYSTEM = """\
你是文字游戏的记忆整理助手：从对话与事件记录中抽取值得长期记住的信息条目，供角色扮演时回忆参考。
要求：
- 只记录确定发生过的内容，不臆测、不扩写；忽略寒暄与无关细节。
- 每条独立成条，一句话以内，以「她」「玩家」指代双方，突出关系变化与关键事实。
- kind 取值：fact（客观事实）/ event（发生过的事件）/ relationship（关系与情感变化）/ promise（约定与承诺）。
- importance 1-10：日常琐事 1-3，较重要 4-6，重要转折 7-8，极其重要 9-10。
- 已有记忆里出现过的内容不要重复输出；没有值得记录的内容就输出空数组 []。
只输出 JSON 数组，不要输出任何其他文字。示例：
[{"kind":"event","content":"她在雨夜被玩家收留，最初整夜不敢合眼。","importance":8}]"""


# ── 纯函数区 ──

def parse_summary(raw: str | None) -> list[dict] | None:
    """解析总结输出为条目列表；失败返回 None（区别于合法空数组）。"""
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\[.*\]", text, re.S)
        if match:
            try:
                data = json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                data = None
    if not isinstance(data, list):
        return None
    entries: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        kind = str(item.get("kind") or "fact").strip().lower()
        if kind not in KINDS:
            kind = "fact"
        try:
            importance = int(round(float(item.get("importance", 5))))
        except (TypeError, ValueError):
            importance = 5
        importance = max(1, min(10, importance))
        entries.append({
            "kind": kind,
            "content": content[:_MAX_CONTENT_CHARS],
            "importance": importance,
        })
    return entries


def merge_entries(
    entries: list[dict] | None, existing_contents: set[str] | None = None
) -> tuple[list[dict], int]:
    """与已有记忆及本次内部去重，返回 (新增条目, 跳过数)。"""
    existing = {c.strip() for c in (existing_contents or set()) if c and c.strip()}
    new_entries: list[dict] = []
    skipped = 0
    for entry in entries or []:
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        if content in existing:
            skipped += 1
            continue
        existing.add(content)
        new_entries.append({**entry, "content": content})
    return new_entries, skipped


def memory_score(importance: int | float, age_hours: float) -> float:
    """重要性 × 新近度：新记忆获得最高约 2 倍加成，随时间衰减到 1 倍。"""
    try:
        base = float(importance)
    except (TypeError, ValueError):
        base = 5.0
    age_days = max(0.0, float(age_hours)) / 24.0
    return base * (1.0 + 1.0 / (1.0 + age_days))


def select_memories(
    items: list[dict], *, budget: int = MEMORY_CHAR_BUDGET, now: datetime | None = None
) -> list[dict]:
    """核心记忆（relationship / importance≥8）常驻，其余按分数填充字符预算。"""
    now = now or datetime.now()
    scored: list[tuple[bool, float, dict]] = []
    for item in items:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        try:
            importance = int(item.get("importance", 5))
        except (TypeError, ValueError):
            importance = 5
        created = item.get("created_at")
        age_hours = 0.0
        if isinstance(created, datetime):
            age_hours = max(0.0, (now - created).total_seconds() / 3600.0)
        core = str(item.get("kind") or "") == "relationship" or importance >= CORE_IMPORTANCE
        scored.append((core, memory_score(importance, age_hours), item))
    scored.sort(key=lambda x: x[1], reverse=True)

    selected: list[dict] = []
    used = 0
    for core, _score, item in scored:
        if not core:
            continue
        cost = len(str(item.get("content") or "")) + 12
        if used + cost > budget:
            continue
        selected.append(item)
        used += cost
    for core, _score, item in scored:
        if core:
            continue
        cost = len(str(item.get("content") or "")) + 12
        if used + cost > budget:
            continue
        selected.append(item)
        used += cost
    return selected


def timeline_lines(messages: list, logs: list) -> list[str]:
    """把消息与事件日志整理为按虚拟时间排序的文本时间线。"""
    role_names = {"user": "玩家", "assistant": "角色", "event": "事件", "system": "系统"}
    items: list[tuple[int, int, int, str]] = []
    for m in messages:
        content = str(getattr(m, "content", "") or "").strip()
        if not content:
            continue
        role = role_names.get(str(getattr(m, "role", "")), "记录")
        items.append((
            int(getattr(m, "game_minutes_at", 0) or 0),
            0,
            int(getattr(m, "id", 0) or 0),
            f"[{role}] {content}",
        ))
    for log in logs:
        meta = getattr(log, "meta", None) or {}
        name = meta.get("name") or meta.get("key") or "事件"
        content = str(getattr(log, "content", "") or "").strip()
        if not content:
            continue
        items.append((
            int(getattr(log, "game_minutes_at", 0) or 0),
            1,
            int(getattr(log, "id", 0) or 0),
            f"[事件·{name}] {content}",
        ))
    items.sort(key=lambda x: (x[0], x[1], x[2]))
    return [text for *_, text in items]


def clip_lines(lines: list[str], budget: int = MEMORY_PROMPT_CHAR_BUDGET) -> list[str]:
    """按字符预算保留最近的内容（从后往前累计后恢复正序）。"""
    kept: list[str] = []
    used = 0
    for line in reversed(lines):
        if used + len(line) > budget:
            break
        kept.append(line)
        used += len(line) + 1
    kept.reverse()
    return kept


def build_summary_messages(save: Save, messages: list, logs: list, existing: list) -> list[dict]:
    """组装总结请求（system + user），对话原文按预算保留最近部分。"""
    parts: list[str] = []
    if existing:
        parts.append("# 已有记忆（不要重复输出）")
        for row in existing:
            content = str(getattr(row, "content", "") or "").strip()
            if content:
                parts.append(f"- [{getattr(row, 'kind', 'fact')}] {content}")
    lines = clip_lines(timeline_lines(messages, logs))
    if lines:
        parts.append("# 对话与事件记录")
        parts.extend(lines)
    return [
        {"role": "system", "content": SUMMARY_SYSTEM},
        {"role": "user", "content": "\n".join(parts)},
    ]


# ── DB 区 ──

def count_unsummarized(session: Session, save_id: int) -> int:
    save = session.get(Save, save_id)
    if save is None:
        return 0
    return int(
        session.scalar(
            select(func.count(Message.id)).where(
                Message.save_id == save_id,
                Message.id > int(save.last_summarized_message_id or 0),
            )
        )
        or 0
    )


def _has_open_job(session: Session, save_id: int) -> bool:
    return (
        session.scalar(
            select(MemoryJob.id)
            .where(
                MemoryJob.save_id == save_id,
                MemoryJob.status.in_(("pending", "running")),
            )
            .limit(1)
        )
        is not None
    )


def trigger_if_due(session: Session, save_id: int) -> bool:
    """未总结消息达到阈值且无进行中的任务时，登记一个 pending 总结任务。"""
    if count_unsummarized(session, save_id) < MEMORY_TRIGGER_TURNS:
        return False
    if _has_open_job(session, save_id):
        return False
    session.add(MemoryJob(save_id=save_id, status="pending"))
    session.commit()
    return True


def requeue_interrupted(session: Session) -> list[int]:
    """启动补跑：中断的 running 任务回到 pending，返回待执行的存档 id。"""
    rows = list(
        session.scalars(
            select(MemoryJob).where(MemoryJob.status.in_(("pending", "running")))
        )
    )
    save_ids: list[int] = []
    for job in rows:
        if job.status == "running":
            job.status = "pending"
            job.error = ""
        save_ids.append(int(job.save_id))
    if rows:
        session.commit()
    return sorted(set(save_ids))


def _claim_job(session: Session, save_id: int) -> MemoryJob | None:
    """save 级互斥抢占：已有 running 则放弃；条件更新 pending → running。"""
    with save_settle_lock(save_id):
        running = session.scalar(
            select(MemoryJob)
            .where(MemoryJob.save_id == save_id, MemoryJob.status == "running")
            .limit(1)
        )
        if running is not None:
            return None
        job = session.scalar(
            select(MemoryJob)
            .where(MemoryJob.save_id == save_id, MemoryJob.status == "pending")
            .order_by(MemoryJob.id)
            .limit(1)
        )
        if job is None:
            job = MemoryJob(save_id=save_id, status="pending")
            session.add(job)
            session.flush()
        result = session.execute(
            update(MemoryJob)
            .where(MemoryJob.id == job.id, MemoryJob.status == "pending")
            .values(status="running")
        )
        if result.rowcount != 1:
            session.rollback()
            return None
        session.commit()
        return job


def _finish_job(
    session: Session, job_id: int, status: str, error: str = ""
) -> None:
    job = session.get(MemoryJob, job_id)
    if job is not None:
        job.status = status
        job.error = error[:500]


def _prepare_summary(save_id: int) -> dict | None:
    """线程池同步段：抢占任务、收集消息/事件/已有记忆，解析总结模型。

    抢占成功后的任何异常都会把任务落 failed，避免卡在 running 状态。
    """
    session = SessionLocal()
    try:
        save = session.get(Save, save_id)
        if save is None:
            return None
        job = _claim_job(session, save_id)
        if job is None:
            return None
        try:
            messages = list(
                session.scalars(
                    select(Message)
                    .where(
                        Message.save_id == save_id,
                        Message.id > int(save.last_summarized_message_id or 0),
                    )
                    .order_by(Message.id)
                    .limit(MEMORY_MAX_MESSAGES_PER_JOB)
                )
            )
            if not messages:
                _finish_job(session, job.id, "done")
                session.commit()
                return None
            first_at = int(messages[0].game_minutes_at or 0)
            logs = list(
                session.scalars(
                    select(EventLog)
                    .where(
                        EventLog.save_id == save_id,
                        EventLog.game_minutes_at >= first_at,
                    )
                    .order_by(EventLog.id)
                    .limit(MEMORY_MAX_MESSAGES_PER_JOB)
                )
            )
            existing = list(
                session.scalars(
                    select(Memory)
                    .where(Memory.save_id == save_id, Memory.status == "active")
                    .order_by(Memory.created_at.desc())
                    .limit(MEMORY_EXISTING_LIMIT)
                )
            )
            model_key = (
                str((save.settings or {}).get("memory_model") or "").strip()
                or (MEMORY_MODEL or "").strip()
                or save.model_key
            )
            try:
                runtime = get_runtime(session, model_key, http=False)
            except AIClientError as e:
                _finish_job(session, job.id, "failed", str(e))
                session.commit()
                return None
            return {
                "save_id": save_id,
                "job_id": job.id,
                "last_message_id": int(messages[-1].id),
                "prompt_messages": build_summary_messages(save, messages, logs, existing),
                "model_id": runtime["model_id"],
                "base_url": runtime["base_url"],
                "api_key": runtime["api_key"],
                "message_count": len(messages),
            }
        except Exception as e:
            logger.exception("记忆总结准备阶段失败（save=%s job=%s）", save_id, job.id)
            _fail_job_in_session(session, job.id, str(e))
            return None
    finally:
        session.close()


def _fail_job_in_session(session: Session, job_id: int, error: str) -> None:
    """在已打开的会话中安全落失败状态（供准备阶段异常兜底）。"""
    try:
        session.rollback()
        _finish_job(session, job_id, "failed", error)
        session.commit()
    except Exception:
        logger.exception("记忆总结任务失败状态落库失败（job=%s）", job_id)


def _apply_summary(prepared: dict, raw: str) -> dict | None:
    """线程池同步段：解析总结输出、去重合并写入 memories、推进总结进度。"""
    entries = parse_summary(raw)
    session = SessionLocal()
    try:
        job_id = int(prepared["job_id"])
        if entries is None:
            _finish_job(session, job_id, "failed", (raw or "")[:500])
            session.commit()
            return None
        save_id = int(prepared["save_id"])
        existing_contents = set(
            session.scalars(
                select(Memory.content).where(
                    Memory.save_id == save_id, Memory.status == "active"
                )
            )
        )
        new_entries, skipped = merge_entries(entries, existing_contents)
        added: list[dict] = []
        for entry in new_entries:
            memory = Memory(
                save_id=save_id,
                kind=entry["kind"],
                content=entry["content"],
                importance=entry["importance"],
            )
            session.add(memory)
            session.flush()
            added.append({
                "id": memory.id,
                "kind": memory.kind,
                "content": memory.content,
                "importance": memory.importance,
            })
        save = session.get(Save, save_id)
        if save is not None:
            save.last_summarized_message_id = max(
                int(save.last_summarized_message_id or 0),
                int(prepared["last_message_id"]),
            )
        _finish_job(session, job_id, "done")
        session.commit()
        return {
            "added": added,
            "skipped": skipped,
            "extracted": len(entries),
            "message_count": int(prepared.get("message_count") or 0),
        }
    finally:
        session.close()


async def run_summary(save_id: int) -> dict | None:
    """异步执行一次总结：准备（线程池）→ LLM 调用 → 落库（线程池）。

    任何异常都会把任务标记为 failed，避免任务卡在 running 状态。
    """
    prepared = await run_in_threadpool(_prepare_summary, save_id)
    if prepared is None:
        return None
    try:
        raw = await ai.complete(
            messages=prepared["prompt_messages"],
            model_id=prepared["model_id"],
            base_url=prepared["base_url"],
            api_key=prepared["api_key"],
            max_tokens=MEMORY_SUMMARY_MAX_TOKENS,
        )
    except AIClientError as e:
        await run_in_threadpool(_fail_job, prepared["job_id"], str(e))
        logger.warning("记忆总结调用失败: %s", e)
        return None
    except Exception as e:
        await run_in_threadpool(_fail_job, prepared["job_id"], str(e))
        logger.exception("记忆总结调用异常（save=%s）", save_id)
        return None
    try:
        return await run_in_threadpool(_apply_summary, prepared, raw)
    except Exception as e:
        await run_in_threadpool(_fail_job, prepared["job_id"], str(e))
        logger.exception("记忆总结落库异常（save=%s）", save_id)
        return None


def _fail_job(job_id: int, error: str) -> None:
    session = SessionLocal()
    try:
        job = session.get(MemoryJob, job_id)
        if job is not None and job.status != "done":
            _finish_job(session, job_id, "failed", error)
        session.commit()
    finally:
        session.close()


async def safe_run_summary(save_id: int) -> None:
    """后台任务入口：吞掉异常，避免未处理任务异常影响服务。"""
    try:
        await run_summary(save_id)
    except Exception:
        logger.exception("记忆总结任务异常（save=%s）", save_id)


def retrieve(session: Session, save_id: int) -> list[dict]:
    """检索待注入的永久记忆（核心常驻 + 预算填充，按分数排序）。"""
    rows = list(
        session.scalars(
            select(Memory).where(
                Memory.save_id == save_id, Memory.status == "active"
            )
        )
    )
    items = [
        {
            "id": row.id,
            "kind": row.kind,
            "content": row.content,
            "importance": row.importance,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    selected = select_memories(items)
    return [
        {"id": item["id"], "kind": item["kind"], "content": item["content"], "importance": item["importance"]}
        for item in selected
    ]


def mark_recalled(session: Session, memory_ids: list[int]) -> None:
    """更新被注入记忆的召回时间与次数（供后续评估与排序使用）。"""
    if not memory_ids:
        return
    now = datetime.now()
    rows = session.scalars(select(Memory).where(Memory.id.in_(memory_ids)))
    for row in rows:
        row.last_recalled_at = now
        row.recall_count = int(row.recall_count or 0) + 1
