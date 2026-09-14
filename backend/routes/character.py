"""
女主角设定书 — 全局唯一，内置种子装载（seeds/character.json），仅提供读取。

设定书不在游戏界面暴露编辑；修改设定 = 修改种子文件后重启。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_session
from helpers import character_dict, get_global_character

router = APIRouter(tags=["character"])


@router.get("/api/character")
def get_character(session: Session = Depends(get_session)):
    return character_dict(get_global_character(session))
