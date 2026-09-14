"""
路由共享辅助函数 — 错误格式、目录解析、序列化。
"""
from __future__ import annotations

import os
import re
import threading

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import DEFAULT_MAX_TOKENS, DUMMY_API_KEY
from orm import AttributeDef, AttributeValue, CatalogModel, Character, Provider, Save

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


def find_model_key_references(session: Session, model_key: str) -> list[str]:
    """返回引用该模型 key 的存档名列表（删除保护用）。"""
    names = [
        s.name
        for s in session.scalars(select(Save).where(Save.model_key == model_key))
    ]
    return names


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
        "updated_at": character.updated_at,
    }


def get_global_character(session: Session) -> Character | None:
    """全局唯一女主角（取最早创建的一条）。"""
    return session.scalar(select(Character).order_by(Character.id).limit(1))


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
