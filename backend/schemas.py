"""
Pydantic 请求模型 — 仅定义入参；响应用普通 dict 组装。
"""
from __future__ import annotations

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
    status: str | None = Field(default=None, max_length=16)
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
