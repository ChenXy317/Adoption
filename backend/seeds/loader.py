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
from orm import AttributeDef, Character, EventDef, Save, SceneDef

logger = logging.getLogger(__name__)


def apply_seeds(session: Session) -> None:
    """装载内置属性定义（seeds/attributes.json 为准，覆盖同名定义的字段）。

    种子未提供的字段保持库内原值（enabled 不受种子影响）；default_value 会钳制到 min/max。
    """
    path = SEEDS_DIR / "attributes.json"
    if not path.exists():
        logger.warning("未找到种子文件: %s", path)
        return
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    existing = {d.key: d for d in session.scalars(select(AttributeDef))}
    added = updated = 0
    for item in items:
        key = (item.get("key") or "").strip()
        if not key:
            continue
        definition = existing.get(key)
        raw_default = item.get("default_value", 0)
        lo = float(item.get("min", 0))
        hi = float(item.get("max", 100))
        if definition is None:
            session.add(
                AttributeDef(
                    key=key,
                    name=item.get("name") or key,
                    category=item.get("category", "stat"),
                    min=lo,
                    max=hi,
                    default_value=min(max(float(raw_default), lo), hi),
                    tick_rule=item.get("tick_rule"),
                    ai_editable=bool(item.get("ai_editable", True)),
                    sort=int(item.get("sort", 0)),
                    enabled=True,
                )
            )
            added += 1
            continue
        fields: dict = {}
        for name in (
            "name",
            "category",
            "min",
            "max",
            "default_value",
            "tick_rule",
            "ai_editable",
            "sort",
        ):
            if name in item:
                fields[name] = item[name]
        if not fields:
            continue
        lo = float(fields.get("min", definition.min))
        hi = float(fields.get("max", definition.max))
        if lo >= hi:
            logger.warning("属性种子 %s 的 min/max 非法，已跳过更新", key)
            continue
        if "name" in fields:
            fields["name"] = str(fields["name"] or key)
        if "category" in fields:
            fields["category"] = str(fields["category"] or "stat")
        if "ai_editable" in fields:
            fields["ai_editable"] = bool(fields["ai_editable"])
        if "sort" in fields:
            fields["sort"] = int(fields["sort"] or 0)
        if "default_value" in fields:
            fields["default_value"] = min(max(float(fields["default_value"]), lo), hi)
        if any(getattr(definition, name) != value for name, value in fields.items()):
            for name, value in fields.items():
                setattr(definition, name, value)
            updated += 1
    if added or updated:
        session.commit()
        logger.info("属性种子装载完成：新增 %d 条，更新 %d 条", added, updated)


def apply_event_seeds(session: Session) -> None:
    """装载内置事件定义（seeds/events.json 为准，覆盖同名事件的字段）。

    已存在的自定义事件不被删除；种子中移除的事件保持库内原样，便于临时调试。
    """
    path = SEEDS_DIR / "events.json"
    if not path.exists():
        logger.warning("未找到事件种子文件: %s", path)
        return
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    existing = {
        row.key: row for row in session.scalars(select(EventDef))
    }
    added = updated = 0
    for item in items:
        key = (item.get("key") or "").strip()
        if not key:
            continue
        fields = {
            "name": item.get("name") or key,
            "category": item.get("category", "fixed"),
            "trigger": item.get("trigger") or {},
            "cost": item.get("cost") or {},
            "effects": item.get("effects") or {},
            "prompt_template": item.get("prompt_template") or "",
            "once": bool(item.get("once", False)),
            "cooldown_minutes": int(item.get("cooldown_minutes", 0) or 0),
            "priority": int(item.get("priority", 0) or 0),
            "enabled": bool(item.get("enabled", True)),
        }
        definition = existing.get(key)
        if definition is None:
            session.add(EventDef(key=key, **fields))
            added += 1
            continue
        if any(getattr(definition, name) != value for name, value in fields.items()):
            for name, value in fields.items():
                setattr(definition, name, value)
            updated += 1
    if added or updated:
        session.commit()
        logger.info("事件种子装载完成：新增 %d 条，更新 %d 条", added, updated)


def apply_scene_seeds(session: Session) -> None:
    """装载内置场景定义（seeds/scenes.json 为准，覆盖同名场景的字段）。

    与事件种子一致：已存在的自定义场景不被删除；种子移除的场景保持库内原样。
    """
    path = SEEDS_DIR / "scenes.json"
    if not path.exists():
        logger.warning("未找到场景种子文件: %s", path)
        return
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    existing = {row.key: row for row in session.scalars(select(SceneDef))}
    added = updated = 0
    for item in items:
        key = (item.get("key") or "").strip()
        if not key:
            continue
        fields = {
            "name": item.get("name") or key,
            "category": item.get("category", "story"),
            "enter_trigger": item.get("enter_trigger") or {},
            "enter_cost": item.get("enter_cost") or {},
            "scene_prompt": item.get("scene_prompt") or "",
            "goal": item.get("goal") or "",
            "min_turns": int(item.get("min_turns", 3) or 0),
            "max_turns": int(item.get("max_turns", 12) or 0),
            "exit": item.get("exit") or {},
            "effects": item.get("effects") or {},
            "next_scenes": item.get("next_scenes") or [],
            "once": bool(item.get("once", False)),
            "cooldown_minutes": int(item.get("cooldown_minutes", 0) or 0),
            "priority": int(item.get("priority", 0) or 0),
            "enabled": bool(item.get("enabled", True)),
        }
        definition = existing.get(key)
        if definition is None:
            session.add(SceneDef(key=key, **fields))
            added += 1
            continue
        if any(getattr(definition, name) != value for name, value in fields.items()):
            for name, value in fields.items():
                setattr(definition, name, value)
            updated += 1
    if added or updated:
        session.commit()
        logger.info("场景种子装载完成：新增 %d 条，更新 %d 条", added, updated)


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
