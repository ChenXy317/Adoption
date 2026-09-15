"""
ORM 数据模型 — 全部表定义（PLAN 第 4 节）。

所有时间列为本地时区 naive DATETIME；JSON 列对应 MySQL JSON 类型。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Save(Base):
    __tablename__ = "saves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    model_key: Mapped[str] = mapped_column(String(192), default="", nullable=False)
    game_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_summarized_message_id: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class Character(Base):
    """全局唯一的女主角设定书（跨存档共享）。"""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    relation: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    persona: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    freeform: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class AttributeDef(Base):
    __tablename__ = "attribute_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="stat", nullable=False)
    min: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    max: Mapped[float] = mapped_column(Double, default=100.0, nullable=False)
    default_value: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    tick_rule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_editable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AttributeValue(Base):
    __tablename__ = "attribute_values"

    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), primary_key=True
    )
    attr_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class EventDef(Base):
    __tablename__ = "event_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="fixed", nullable=False)
    trigger: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    cost: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    effects: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, default="", nullable=False)
    once: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_defs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="triggered", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    game_minutes_at: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (Index("ix_event_logs_save_time", "save_id", "id"),)


class SceneDef(Base):
    __tablename__ = "scene_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="story", nullable=False)
    enter_trigger: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enter_cost: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scene_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    goal: Mapped[str] = mapped_column(Text, default="", nullable=False)
    min_turns: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_turns: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    exit: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    effects: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    next_scenes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    once: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SceneLog(Base):
    __tablename__ = "scene_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), nullable=False
    )
    scene_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="started", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    game_minutes_at: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(MEDIUMTEXT, default="", nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    game_minutes_at: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (Index("ix_messages_save_id_id", "save_id", "id"),)


class SaveFlag(Base):
    __tablename__ = "save_flags"

    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), default="fact", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    source_from_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_to_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_recalled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recall_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MemoryJob(Base):
    __tablename__ = "memory_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    api_key: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    use_env_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_key_env: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class CatalogModel(Base):
    __tablename__ = "catalog_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uniq_provider_model"),
    )
