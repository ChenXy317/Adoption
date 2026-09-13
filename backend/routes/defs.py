"""
定义读取 — 属性定义与角色人设模板（管理 CRUD 属 M2/M3 阶段）。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import SEEDS_DIR
from db import get_session
from orm import AttributeDef

router = APIRouter(tags=["defs"])


@router.get("/api/attribute-defs")
def list_attribute_defs(session: Session = Depends(get_session)):
    defs = session.scalars(
        select(AttributeDef).order_by(AttributeDef.sort, AttributeDef.id)
    ).all()
    return [
        {
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
        for d in defs
    ]


@router.get("/api/character-templates")
def list_character_templates():
    path = SEEDS_DIR / "templates.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)
