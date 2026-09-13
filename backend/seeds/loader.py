"""
种子数据装载 — 启动时按 key 补齐默认属性定义（不覆盖用户已有修改）。
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import SEEDS_DIR
from orm import AttributeDef

logger = logging.getLogger(__name__)


def apply_seeds(session: Session) -> None:
    path = SEEDS_DIR / "attributes.json"
    if not path.exists():
        logger.warning("未找到种子文件: %s", path)
        return
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    existing = {d.key for d in session.scalars(select(AttributeDef))}
    added = 0
    for item in items:
        key = item.get("key")
        if not key or key in existing:
            continue
        session.add(
            AttributeDef(
                key=key,
                name=item.get("name") or key,
                category=item.get("category", "stat"),
                min=item.get("min", 0),
                max=item.get("max", 100),
                default_value=item.get("default_value", 0),
                tick_rule=item.get("tick_rule"),
                ai_editable=bool(item.get("ai_editable", True)),
                sort=int(item.get("sort", 0)),
                enabled=True,
            )
        )
        added += 1
    if added:
        session.commit()
        logger.info("已写入 %d 条默认属性定义", added)
