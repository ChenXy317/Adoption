"""
路由共享辅助函数 — 错误格式、目录解析、序列化。
"""
from __future__ import annotations

import os
import re
import threading

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import (
    CALENDAR_DEFAULT,
    DEFAULT_MAX_TOKENS,
    DUMMY_API_KEY,
    NEGLECT_AFFECTION_MAX,
    NEGLECT_AFFECTION_PER_DAY,
    NEGLECT_DAYS,
    TIME_DEFAULT_ADVANCE,
    TIME_MAX_ADVANCE_PER_MESSAGE,
    TIME_MAX_JUMP_HOURS,
)
from game import clock
from orm import (
    AttributeDef,
    AttributeValue,
    CatalogModel,
    Character,
    EventLog,
    Message,
    Provider,
    Save,
)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

_save_locks: dict[int, threading.Lock] = {}
_save_locks_guard = threading.Lock()


def save_settle_lock(save_id: int) -> threading.Lock:
    """同一存档的结算事务串行化，避免流后结算与推进/手动事件并发覆盖。"""
    with _save_locks_guard:
        lock = _save_locks.get(save_id)
        if lock is None:
            lock = threading.Lock()
            _save_locks[save_id] = lock
        return lock


def drop_save_lock(save_id: int) -> None:
    """存档删除后释放对应锁，避免锁表随存档数量增长。"""
    with _save_locks_guard:
        _save_locks.pop(save_id, None)


def _clamp_int(value, lo: int, hi: int, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, result))


def sanitize_settings(raw, base: dict | None = None) -> dict:
    """钳制存档设置的关键数值（导入/更新共用）；base 提供局部覆盖字段的兜底值。"""
    if not isinstance(raw, dict):
        return {}
    prior = base if isinstance(base, dict) else {}
    out = dict(raw)

    advance = out.get("advance")
    if isinstance(advance, dict):
        prior_advance = prior.get("advance")
        prior_advance = prior_advance if isinstance(prior_advance, dict) else {}
        cap = TIME_MAX_JUMP_HOURS * 60
        out["advance"] = {
            "default_minutes": _clamp_int(
                advance.get("default_minutes"),
                0,
                cap,
                _clamp_int(prior_advance.get("default_minutes"), 0, cap, TIME_DEFAULT_ADVANCE),
            ),
            "max_per_message": _clamp_int(
                advance.get("max_per_message"),
                1,
                cap,
                _clamp_int(
                    prior_advance.get("max_per_message"), 1, cap,
                    TIME_MAX_ADVANCE_PER_MESSAGE,
                ),
            ),
        }

    calendar = out.get("calendar")
    if isinstance(calendar, dict):
        prior_calendar = prior.get("calendar")
        prior_calendar = prior_calendar if isinstance(prior_calendar, dict) else {}

        def calendar_value(key: str, lo: int, hi: int) -> int:
            return _clamp_int(
                calendar.get(key),
                lo,
                hi,
                _clamp_int(prior_calendar.get(key), lo, hi, CALENDAR_DEFAULT[key]),
            )

        out["calendar"] = {
            "month": calendar_value("month", 1, 12),
            "day": calendar_value("day", 1, clock.MONTH_DAYS),
            "hour": calendar_value("hour", 0, 23),
            "minute": calendar_value("minute", 0, 59),
        }

    neglect = out.get("neglect")
    if isinstance(neglect, dict):
        prior_neglect = prior.get("neglect")
        prior_neglect = prior_neglect if isinstance(prior_neglect, dict) else {}

        def neglect_value(key: str, lo: int, hi: int, default: int) -> int:
            return _clamp_int(
                neglect.get(key),
                lo,
                hi,
                _clamp_int(prior_neglect.get(key), lo, hi, default),
            )

        out["neglect"] = {
            "days": neglect_value("days", 0, 365, NEGLECT_DAYS),
            "per_day": neglect_value("per_day", 0, 10, NEGLECT_AFFECTION_PER_DAY),
            "max": neglect_value("max", 0, 100, NEGLECT_AFFECTION_MAX),
        }

    if "content_prompt" in out and not isinstance(out["content_prompt"], str):
        out["content_prompt"] = ""
    if "memory_model" in out and not isinstance(out["memory_model"], str):
        out["memory_model"] = ""
    return out


def error(code: str, message: str, status: int = 400, detail: str = "") -> None:
    raise HTTPException(
        status_code=status,
        detail={"code": code, "message": message, "detail": detail},
    )


def get_save_or_error(session: Session, save_id: int) -> Save:
    save = session.get(Save, save_id)
    if save is None:
        error("save_not_found", f"存档 {save_id} 不存在", 404)
    return save


def normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        error("invalid_base_url", "基础 URL 必须以 http:// 或 https:// 开头", 400)
    return u.rstrip("/")


def validate_slug(slug: str) -> str:
    s = (slug or "").strip()
    if not SLUG_RE.match(s):
        error(
            "invalid_slug",
            "供应商 ID 须以小写字母或数字开头，只能包含小写字母、数字、连字符或下划线",
            400,
        )
    return s


def resolve_secret(row: Provider) -> str:
    """从目录行解析调用用的 API Key；环境变量缺失时抛 ValueError。"""
    if row.use_env_key:
        env_name = (row.api_key_env or "").strip()
        if not env_name:
            raise ValueError("该供应商已勾选从环境变量读取，但未填写变量名")
        val = os.environ.get(env_name, "")
        if not val:
            raise ValueError(f"环境变量 {env_name} 未设置或为空")
        return val
    key = (row.api_key or "").strip()
    return key or DUMMY_API_KEY


def public_provider(row: Provider, models: list[CatalogModel]) -> dict:
    """对外返回供应商（不含密钥明文）。"""
    items = []
    for m in models:
        mid = m.model_id
        items.append({
            "id": m.id,
            "model_id": mid,
            "display_name": (m.display_name or "").strip() or mid,
            "key": f"{row.slug}:{mid}",
        })
    use_env = bool(row.use_env_key)
    env_name = (row.api_key_env or "").strip()
    if use_env:
        key_ready = bool(env_name and os.environ.get(env_name))
    else:
        key_ready = True
    return {
        "id": row.id,
        "slug": row.slug,
        "display_name": row.display_name or row.slug,
        "base_url": row.base_url or "",
        "use_env_key": use_env,
        "api_key_env": env_name,
        "has_api_key": bool((row.api_key or "").strip()),
        "key_ready": key_ready,
        "models": items,
        "sort_order": row.sort_order or 0,
    }


def get_runtime(session: Session, model_key: str, *, http: bool = True) -> dict:
    """解析对话/测试用的运行时配置。http=False 时抛 AIClientError 而非 HTTP 错误。"""
    from ai_client import AIClientError

    def fail(msg: str):
        if http:
            error("unknown_model", msg, 400)
        raise AIClientError(msg, "unknown_model")

    if not model_key or ":" not in model_key:
        fail(f"模型不存在或已从目录删除: {model_key}")
    slug, model_id = model_key.split(":", 1)
    row = session.execute(
        select(CatalogModel, Provider)
        .join(Provider, CatalogModel.provider_id == Provider.id)
        .where(Provider.slug == slug, CatalogModel.model_id == model_id)
    ).first()
    if not row:
        fail(f"模型不存在或已从目录删除: {model_key}")
    catalog_model, provider = row
    try:
        api_key = resolve_secret(provider)
    except ValueError as e:
        if http:
            error("missing_api_key", str(e), 400)
        raise AIClientError(str(e), "missing_api_key") from e
    return {
        "model_id": catalog_model.model_id,
        "base_url": provider.base_url or "",
        "api_key": api_key,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "display_name": (catalog_model.display_name or "").strip()
        or catalog_model.model_id,
    }


def character_dict(character: Character | None) -> dict | None:
    if character is None:
        return None
    return {
        "id": character.id,
        "name": character.name,
        "age": character.age,
        "relation": character.relation,
        "persona": character.persona or {},
        "freeform": character.freeform or "",
        "user_edited": bool(character.user_edited),
        "updated_at": character.updated_at,
    }


def get_global_character(session: Session) -> Character | None:
    """全局唯一女主角（取最早创建的一条）。"""
    return session.scalar(select(Character).order_by(Character.id).limit(1))


def get_save_character(session: Session, save: Save) -> Character | None:
    """存档关联的女主角；引用缺失时回退到全局女主角（自愈旧数据）。"""
    if save.character_id:
        character = session.get(Character, save.character_id)
        if character is not None:
            return character
    return get_global_character(session)


def attribute_items(
    defs: list[AttributeDef], values: dict[str, float]
) -> list[dict]:
    items = []
    for d in defs:
        if not d.enabled:
            continue
        items.append({
            "key": d.key,
            "name": d.name,
            "category": d.category,
            "min": d.min,
            "max": d.max,
            "value": values.get(d.key, d.default_value),
            "ai_editable": bool(d.ai_editable),
            "sort": d.sort,
        })
    return items


def load_attr_values(session: Session, save_id: int) -> dict[str, float]:
    rows = session.scalars(
        select(AttributeValue).where(AttributeValue.save_id == save_id)
    )
    return {r.attr_key: r.value for r in rows}


def behavior_count(session: Session, save_id: int) -> int:
    """互动计数：玩家发言数 + 已触发事件数（性格倾向推导用）。"""
    user_messages = session.scalar(
        select(func.count(Message.id)).where(
            Message.save_id == save_id, Message.role == "user"
        )
    ) or 0
    triggered = session.scalar(
        select(func.count(EventLog.id)).where(EventLog.save_id == save_id)
    ) or 0
    return int(user_messages) + int(triggered)
