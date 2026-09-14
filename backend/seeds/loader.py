"""
种子数据装载 — 启动时补齐属性定义，并装载内置女主角设定书。

女主角为完全设计好的内置内容（seeds/character.json 为唯一真相源，
以种子为准覆盖库中记录）；属性定义按 key 补齐，不覆盖已有修改。
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import SEEDS_DIR
from orm import AttributeDef, Character, Save

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


def apply_character_seed(session: Session) -> None:
    """从 seeds/character.json 装载全局女主角（种子为准，覆盖库中记录）。"""
    path = SEEDS_DIR / "character.json"
    if not path.exists():
        logger.warning("未找到女主角种子文件: %s", path)
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    fields = {
        "name": (data.get("name") or "").strip() or "她",
        "age": max(18, int(data.get("age") or 18)),
        "relation": (data.get("relation") or "").strip(),
        "persona": data.get("persona") or {},
        "freeform": data.get("freeform") or "",
    }
    character = session.scalar(select(Character).order_by(Character.id).limit(1))
    if character is None:
        character = Character(**fields)
        session.add(character)
        session.flush()
        for save in session.scalars(
            select(Save).where(Save.character_id.is_(None))
        ):
            save.character_id = character.id
        session.commit()
        logger.info("已从种子创建女主角「%s」", fields["name"])
        return
    changed = (
        character.name != fields["name"]
        or character.age != fields["age"]
        or character.relation != fields["relation"]
        or (character.persona or {}) != fields["persona"]
        or (character.freeform or "") != fields["freeform"]
    )
    if changed:
        for key, value in fields.items():
            setattr(character, key, value)
        session.commit()
        logger.info("已从种子更新女主角「%s」", fields["name"])
