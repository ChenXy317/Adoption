"""
定义管理 — 属性定义 CRUD（PLAN 5.2，界面不暴露编辑，供种子/维护使用）。

属性 key 创建后不可改（避免孤儿属性值），仅支持启停与数值范围调整。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db import get_session
from game.attributes import clamp
from helpers import error
from orm import AttributeDef, AttributeValue
from schemas import AttributeDefIn, AttributeDefPatch

router = APIRouter(tags=["defs"])


def _def_dict(d: AttributeDef) -> dict:
    return {
        "id": d.id,
        "key": d.key,
        "name": d.name,
        "category": d.category,
        "min": d.min,
        "max": d.max,
        "default_value": d.default_value,
        "tick_rule": d.tick_rule,
        "ai_editable": bool(d.ai_editable),
        "sort": d.sort,
        "enabled": bool(d.enabled),
    }


@router.get("/api/attribute-defs")
def list_attribute_defs(session: Session = Depends(get_session)):
    defs = session.scalars(
        select(AttributeDef).order_by(AttributeDef.sort, AttributeDef.id)
    ).all()
    return [_def_dict(d) for d in defs]


@router.post("/api/attribute-defs")
def create_attribute_def(
    req: AttributeDefIn, session: Session = Depends(get_session)
):
    exists = session.scalar(
        select(AttributeDef).where(AttributeDef.key == req.key)
    )
    if exists:
        error("duplicate_key", f"属性 key「{req.key}」已存在", 409)
    if req.min >= req.max:
        error("invalid_range", "最小值必须小于最大值", 400)
    definition = AttributeDef(
        key=req.key,
        name=req.name.strip(),
        category=req.category.strip() or "stat",
        min=req.min,
        max=req.max,
        default_value=clamp(req.default_value, req.min, req.max),
        tick_rule=req.tick_rule,
        ai_editable=req.ai_editable,
        sort=req.sort,
        enabled=req.enabled,
    )
    session.add(definition)
    session.commit()
    return _def_dict(definition)


@router.patch("/api/attribute-defs/{def_id}")
def update_attribute_def(
    def_id: int, req: AttributeDefPatch, session: Session = Depends(get_session)
):
    definition = session.get(AttributeDef, def_id)
    if definition is None:
        error("def_not_found", "属性不存在", 404)
    if req.name is not None:
        definition.name = req.name.strip()
    if req.category is not None:
        definition.category = req.category.strip() or "stat"
    if req.min is not None:
        definition.min = req.min
    if req.max is not None:
        definition.max = req.max
    if definition.min >= definition.max:
        error("invalid_range", "最小值必须小于最大值", 400)
    if req.default_value is not None:
        definition.default_value = req.default_value
    definition.default_value = clamp(
        definition.default_value, definition.min, definition.max
    )
    if "tick_rule" in req.model_fields_set:
        definition.tick_rule = req.tick_rule
    if req.ai_editable is not None:
        definition.ai_editable = req.ai_editable
    if req.sort is not None:
        definition.sort = req.sort
    if req.enabled is not None:
        definition.enabled = req.enabled
    for value_row in session.scalars(
        select(AttributeValue).where(AttributeValue.attr_key == definition.key)
    ):
        value_row.value = clamp(value_row.value, definition.min, definition.max)
    session.commit()
    return _def_dict(definition)


@router.delete("/api/attribute-defs/{def_id}")
def delete_attribute_def(
    def_id: int, session: Session = Depends(get_session)
):
    definition = session.get(AttributeDef, def_id)
    if definition is None:
        error("def_not_found", "属性不存在", 404)
    session.execute(
        delete(AttributeValue).where(AttributeValue.attr_key == definition.key)
    )
    session.execute(delete(AttributeDef).where(AttributeDef.id == def_id))
    session.commit()
    return {"ok": True}
