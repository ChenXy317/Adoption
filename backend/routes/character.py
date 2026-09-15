"""
女主角设定书 — 全局唯一，内置种子装载（seeds/character.json）。

用户可在界面上直接修改设定书：修改后标记 user_edited，种子不再覆盖，
并可通过「恢复内置设定」回到 seeds/character.json 的内容。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import SEEDS_DIR
from db import get_session
from helpers import character_dict, error, get_global_character
from schemas import CharacterPatch
from seeds.loader import character_seed_fields

router = APIRouter(tags=["character"])

PERSONA_TEXT_MAX = 4000
PERSONA_LIST_MAX = 200
PERSONA_DEPTH_MAX = 3


def _clean_persona(value, depth: int = 0):
    """限制设定书 JSON 的结构与体积（字符串截断、列表/字典限量、限制嵌套深度）。"""
    if depth > PERSONA_DEPTH_MAX:
        return None
    if isinstance(value, str):
        return value[:PERSONA_TEXT_MAX]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        items = [_clean_persona(item, depth + 1) for item in value[:PERSONA_LIST_MAX]]
        return [item for item in items if item is not None]
    if isinstance(value, dict):
        out: dict = {}
        for key, item in list(value.items())[:64]:
            cleaned = _clean_persona(item, depth + 1)
            if cleaned is not None:
                out[str(key)[:64]] = cleaned
        return out
    return None


@router.get("/api/character")
def get_character(session: Session = Depends(get_session)):
    return character_dict(get_global_character(session))


@router.patch("/api/character")
def update_character(
    req: CharacterPatch, session: Session = Depends(get_session)
):
    """编辑女主角设定书；修改后不再被种子覆盖。"""
    character = get_global_character(session)
    if character is None:
        error("character_not_found", "女主角设定书不存在", 404)
    fields = req.model_dump(exclude_unset=True)
    if fields.get("name") is not None:
        character.name = str(fields["name"]).strip()[:64]
    if fields.get("age") is not None:
        character.age = int(fields["age"])
    if fields.get("relation") is not None:
        character.relation = str(fields["relation"]).strip()[:64]
    if req.persona is not None:
        if not isinstance(req.persona, dict):
            error("invalid_persona", "persona 必须是结构化设定对象", 400)
        character.persona = _clean_persona(req.persona) or {}
    if fields.get("freeform") is not None:
        character.freeform = str(fields["freeform"])[:20000]
    character.user_edited = True
    session.commit()
    return character_dict(character)


@router.post("/api/character/reset")
def reset_character(session: Session = Depends(get_session)):
    """把设定书恢复为内置种子（seeds/character.json）内容。"""
    character = get_global_character(session)
    if character is None:
        error("character_not_found", "女主角设定书不存在", 404)
    path = SEEDS_DIR / "character.json"
    if not path.exists():
        error("seed_missing", "未找到内置角色书种子文件", 500)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for key, value in character_seed_fields(data).items():
        setattr(character, key, value)
    character.user_edited = False
    session.commit()
    return character_dict(character)
