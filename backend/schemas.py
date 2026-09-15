"""
Pydantic 请求模型 — 仅定义入参；响应用普通 dict 组装。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SaveCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    model_key: str = Field(default="", max_length=192)
    settings: dict | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("存档名不能为空")
        return text


class SaveUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    model_key: str | None = Field(default=None, max_length=192)
    status: Literal["active", "archived"] | None = None
    settings: dict | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("存档名不能为空")
        return text


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)


class AdvanceIn(BaseModel):
    """显式推进时间：minutes 增量 / period 跳到下一时段 / target 跳到指定虚拟时刻。"""

    minutes: int | None = Field(default=None, ge=1, le=100000)
    period: str | None = Field(default=None, max_length=32)
    target: dict | None = None


class SceneEnterIn(BaseModel):
    """手动进入场景（调试）：场景 key。"""

    key: str = Field(min_length=1, max_length=64)


class SceneEndIn(BaseModel):
    """手动结束当前场景：summary 为收尾总结，abort 为强制中止（调试）。"""

    summary: str = Field(default="", max_length=2000)
    abort: bool = False


class MemoryIn(BaseModel):
    """手动新增记忆。"""

    kind: str = Field(default="fact", max_length=16)
    content: str = Field(min_length=1, max_length=2000)
    importance: int = Field(default=5, ge=1, le=10)


class MemoryPatch(BaseModel):
    kind: str | None = Field(default=None, max_length=16)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    importance: int | None = Field(default=None, ge=1, le=10)
    status: str | None = Field(default=None, max_length=16)


class CharacterPatch(BaseModel):
    """女主角设定书编辑；persona 为结构化设定内容。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    age: int | None = Field(default=None, ge=18, le=99)
    relation: str | None = Field(default=None, max_length=64)
    persona: dict | None = None
    freeform: str | None = Field(default=None, max_length=20000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("角色名不能为空")
        return text


class AttributeDefIn(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    name: str = Field(min_length=1, max_length=64)
    category: str = Field(default="stat", max_length=32)
    min: float = 0
    max: float = 100
    default_value: float = 0
    tick_rule: dict | None = None
    ai_editable: bool = True
    sort: int = 0
    enabled: bool = True


class AttributeDefPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=32)
    min: float | None = None
    max: float | None = None
    default_value: float | None = None
    tick_rule: dict | None = None
    ai_editable: bool | None = None
    sort: int | None = None
    enabled: bool | None = None


class EventDefIn(BaseModel):
    """事件定义（新建）；key 创建后不可改。"""

    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    name: str = Field(min_length=1, max_length=64)
    category: str = Field(default="fixed", max_length=32)
    trigger: dict = Field(default_factory=dict)
    cost: dict = Field(default_factory=dict)
    effects: dict = Field(default_factory=dict)
    prompt_template: str = Field(default="", max_length=8000)
    once: bool = False
    cooldown_minutes: int = Field(default=0, ge=0, le=525600)
    priority: int = Field(default=0, ge=-1000, le=1000)
    enabled: bool = True


class EventDefPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=32)
    trigger: dict | None = None
    cost: dict | None = None
    effects: dict | None = None
    prompt_template: str | None = Field(default=None, max_length=8000)
    once: bool | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=525600)
    priority: int | None = Field(default=None, ge=-1000, le=1000)
    enabled: bool | None = None


class SceneDefIn(BaseModel):
    """场景定义（新建）；key 创建后不可改。"""

    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    name: str = Field(min_length=1, max_length=64)
    category: str = Field(default="story", max_length=32)
    enter_trigger: dict = Field(default_factory=dict)
    enter_cost: dict = Field(default_factory=dict)
    scene_prompt: str = Field(default="", max_length=8000)
    goal: str = Field(default="", max_length=2000)
    min_turns: int = Field(default=3, ge=0, le=100)
    max_turns: int = Field(default=12, ge=0, le=100)
    exit: dict = Field(default_factory=dict)
    effects: dict = Field(default_factory=dict)
    next_scenes: list[str] = Field(default_factory=list, max_length=50)
    once: bool = False
    cooldown_minutes: int = Field(default=0, ge=0, le=525600)
    priority: int = Field(default=0, ge=-1000, le=1000)
    enabled: bool = True


class SceneDefPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=32)
    enter_trigger: dict | None = None
    enter_cost: dict | None = None
    scene_prompt: str | None = Field(default=None, max_length=8000)
    goal: str | None = Field(default=None, max_length=2000)
    min_turns: int | None = Field(default=None, ge=0, le=100)
    max_turns: int | None = Field(default=None, ge=0, le=100)
    exit: dict | None = None
    effects: dict | None = None
    next_scenes: list[str] | None = Field(default=None, max_length=50)
    once: bool | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=525600)
    priority: int | None = Field(default=None, ge=-1000, le=1000)
    enabled: bool | None = None


class CatalogModelIn(BaseModel):
    model_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(default="", max_length=64)


class ProviderIn(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str = Field(default="", max_length=256)
    use_env_key: bool = False
    api_key_env: str = Field(default="", max_length=64)
    models: list[CatalogModelIn] = Field(default_factory=list)


class ProviderPatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=256)
    use_env_key: bool | None = None
    api_key_env: str | None = Field(default=None, max_length=64)


class CatalogModelPatch(BaseModel):
    model_id: str | None = Field(default=None, min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=64)
