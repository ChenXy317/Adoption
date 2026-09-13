"""
供应商 / 模型目录路由（PLAN 5.9，单用户无多租户）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_client import ai
from config import DEFAULT_PARAMS, DEFAULT_MAX_TOKENS, MEMORY_MODEL
from db import get_session
from helpers import (
    ENV_NAME_RE,
    error,
    normalize_base_url,
    public_provider,
    resolve_secret,
    validate_slug,
)
from orm import CatalogModel, Provider, Save
from schemas import (
    CatalogModelIn,
    CatalogModelPatch,
    ProviderIn,
    ProviderPatch,
)

router = APIRouter(tags=["catalog"])


def _require_provider(session: Session, provider_id: int) -> Provider:
    row = session.get(Provider, provider_id)
    if row is None:
        error("provider_not_found", "供应商不存在", 404)
    return row


def _require_model(session: Session, provider_id: int, model_row_id: int) -> CatalogModel:
    row = session.get(CatalogModel, model_row_id)
    if row is None or row.provider_id != provider_id:
        error("model_not_found", "模型不存在", 404)
    return row


def _provider_models(session: Session, provider_id: int) -> list[CatalogModel]:
    return list(
        session.scalars(
            select(CatalogModel)
            .where(CatalogModel.provider_id == provider_id)
            .order_by(CatalogModel.id)
        )
    )


def _validate_key_fields(use_env_key: bool, api_key_env: str) -> str:
    env_name = (api_key_env or "").strip()
    if use_env_key:
        if not env_name:
            error("missing_api_key_env", "勾选从环境变量读取时必须填写变量名", 400)
        if not ENV_NAME_RE.match(env_name):
            error("invalid_api_key_env", "环境变量名不合法", 400)
    return env_name


def _save_refs(session: Session, key_prefix: str) -> list[str]:
    """引用了该前缀（模型 key 或 slug:）的存档名。"""
    names = []
    for save in session.scalars(select(Save)):
        keys = [save.model_key or ""]
        memory_model = (save.settings or {}).get("memory_model") or MEMORY_MODEL
        keys.append(memory_model or "")
        if any(k and k.startswith(key_prefix) for k in keys):
            names.append(save.name)
    return names


@router.get("/api/providers")
def list_providers(session: Session = Depends(get_session)):
    providers = session.scalars(
        select(Provider).order_by(Provider.sort_order, Provider.id)
    ).all()
    return [
        public_provider(p, _provider_models(session, p.id)) for p in providers
    ]


@router.post("/api/providers")
def create_provider(req: ProviderIn, session: Session = Depends(get_session)):
    slug = validate_slug(req.slug)
    name = req.display_name.strip()
    if not name:
        error("empty_name", "显示名称不能为空", 400)
    base_url = normalize_base_url(req.base_url)
    env_name = _validate_key_fields(req.use_env_key, req.api_key_env)
    if session.scalar(select(Provider).where(Provider.slug == slug)):
        error("duplicate_slug", "供应商 ID 已存在", 409)
    max_order = session.scalar(select(Provider.sort_order).order_by(Provider.sort_order.desc())) or 0
    provider = Provider(
        slug=slug,
        display_name=name,
        base_url=base_url,
        api_key=req.api_key.strip() if req.api_key else "",
        use_env_key=req.use_env_key,
        api_key_env=env_name,
        sort_order=max_order + 1,
    )
    session.add(provider)
    session.flush()
    seen: set[str] = set()
    for m in req.models:
        model_id = m.model_id.strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        session.add(
            CatalogModel(
                provider_id=provider.id,
                model_id=model_id,
                display_name=m.display_name.strip(),
            )
        )
    session.commit()
    return public_provider(provider, _provider_models(session, provider.id))


@router.patch("/api/providers/{provider_id}")
def update_provider(
    provider_id: int, req: ProviderPatch, session: Session = Depends(get_session)
):
    provider = _require_provider(session, provider_id)
    if req.display_name is not None:
        name = req.display_name.strip()
        if not name:
            error("empty_name", "显示名称不能为空", 400)
        provider.display_name = name
    if req.base_url is not None:
        provider.base_url = normalize_base_url(req.base_url)
    if req.api_key is not None:
        provider.api_key = req.api_key.strip()
    if req.use_env_key is not None:
        provider.use_env_key = req.use_env_key
    if req.api_key_env is not None or req.use_env_key is not None:
        env_name = (
            req.api_key_env if req.api_key_env is not None else provider.api_key_env
        )
        provider.api_key_env = _validate_key_fields(
            bool(provider.use_env_key), env_name or ""
        )
    session.commit()
    return public_provider(provider, _provider_models(session, provider.id))


@router.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: int, session: Session = Depends(get_session)):
    provider = _require_provider(session, provider_id)
    refs = _save_refs(session, f"{provider.slug}:")
    if refs:
        error("in_use", f"无法删除：仍被存档「{'」「'.join(refs)}」引用", 409)
    session.execute(delete(Provider).where(Provider.id == provider_id))
    session.commit()
    return {"ok": True}


@router.post("/api/providers/{provider_id}/models")
def add_model(
    provider_id: int, req: CatalogModelIn, session: Session = Depends(get_session)
):
    provider = _require_provider(session, provider_id)
    model_id = req.model_id.strip()
    if not model_id:
        error("empty_model_id", "model-id 不能为空", 400)
    exists = session.scalar(
        select(CatalogModel).where(
            CatalogModel.provider_id == provider_id,
            CatalogModel.model_id == model_id,
        )
    )
    if exists:
        error("duplicate_model", "该供应商下已存在相同的 model-id", 409)
    model = CatalogModel(
        provider_id=provider_id,
        model_id=model_id,
        display_name=req.display_name.strip(),
    )
    session.add(model)
    session.commit()
    return {
        "id": model.id,
        "model_id": model.model_id,
        "display_name": model.display_name or model.model_id,
        "key": f"{provider.slug}:{model.model_id}",
    }


@router.patch("/api/providers/{provider_id}/models/{model_row_id}")
def update_model(
    provider_id: int,
    model_row_id: int,
    req: CatalogModelPatch,
    session: Session = Depends(get_session),
):
    provider = _require_provider(session, provider_id)
    model = _require_model(session, provider_id, model_row_id)
    model_id = req.model_id.strip() if req.model_id is not None else None
    display_name = req.display_name if req.display_name is None else req.display_name.strip()
    if model_id is None and display_name is None:
        error("no_update", "未提供任何可更新的字段", 400)
    if model_id is not None and not model_id:
        error("empty_model_id", "model-id 不能为空", 400)
    if model_id is not None and model_id != model.model_id:
        duplicate = session.scalar(
            select(CatalogModel).where(
                CatalogModel.provider_id == provider_id,
                CatalogModel.model_id == model_id,
            )
        )
        if duplicate:
            error("duplicate_model", "该供应商下已存在相同的 model-id", 409)
        model.model_id = model_id
    if display_name is not None:
        model.display_name = display_name
    session.commit()
    return {
        "id": model.id,
        "model_id": model.model_id,
        "display_name": model.display_name or model.model_id,
        "key": f"{provider.slug}:{model.model_id}",
    }


@router.delete("/api/providers/{provider_id}/models/{model_row_id}")
def delete_model(
    provider_id: int, model_row_id: int, session: Session = Depends(get_session)
):
    provider = _require_provider(session, provider_id)
    model = _require_model(session, provider_id, model_row_id)
    key = f"{provider.slug}:{model.model_id}"
    refs = _save_refs(session, f"{key}")
    if refs:
        error("in_use", f"无法删除：仍被存档「{'」「'.join(refs)}」引用", 409)
    session.execute(delete(CatalogModel).where(CatalogModel.id == model.id))
    session.commit()
    return {"ok": True}


@router.post("/api/providers/{provider_id}/models/{model_row_id}/test")
async def test_model(
    provider_id: int, model_row_id: int, session: Session = Depends(get_session)
):
    provider = _require_provider(session, provider_id)
    model = _require_model(session, provider_id, model_row_id)
    try:
        api_key = resolve_secret(provider)
    except ValueError as e:
        error("missing_api_key", str(e), 400)
    return await ai.test_hello(
        model_id=model.model_id,
        base_url=provider.base_url,
        api_key=api_key,
    )


@router.get("/api/models")
def list_models(session: Session = Depends(get_session)):
    rows = session.execute(
        select(CatalogModel, Provider)
        .join(Provider, CatalogModel.provider_id == Provider.id)
        .order_by(Provider.sort_order, Provider.id, CatalogModel.id)
    ).all()
    return [
        {
            "key": f"{provider.slug}:{model.model_id}",
            "id": model.model_id,
            "display_name": (model.display_name or "").strip() or model.model_id,
            "provider": provider.slug,
            "provider_name": provider.display_name or provider.slug,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }
        for model, provider in rows
    ]


@router.get("/api/default-params")
def default_params():
    return DEFAULT_PARAMS
