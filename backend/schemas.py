"""
Pydantic 请求模型 — 仅定义入参；响应用普通 dict 组装。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    age: int = Field(ge=18, le=999)
    relation: str = Field(default="朋友", max_length=64)
    persona: dict = Field(default_factory=dict)
    freeform: str = Field(default="", max_length=20000)
    template_key: str = Field(default="", max_length=64)


class SaveCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    model_key: str = Field(default="", max_length=192)
    character: CharacterIn | None = None
    settings: dict | None = None


class SaveUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    model_key: str | None = Field(default=None, max_length=192)
    status: str | None = Field(default=None, max_length=16)
    settings: dict | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)


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
