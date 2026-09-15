"""
数据库连接与会话管理 — SQLAlchemy 2.0 同步引擎 + pymysql。

启动时自动创建数据库（若不存在）并建表。
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import (
    MYSQL_CHARSET,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)

logger = logging.getLogger(__name__)

if not MYSQL_PASSWORD or not MYSQL_PASSWORD.strip():
    raise RuntimeError(
        "MYSQL_PASSWORD 环境变量未设置或为空！请在系统环境变量或项目根 .env 中设置。"
    )


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset={MYSQL_CHARSET}",
    pool_size=5,
    max_overflow=5,
    pool_recycle=3600,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_database() -> None:
    """确保目标数据库存在，不存在则自动创建。"""
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset=MYSQL_CHARSET,
        )
    except pymysql.Error as e:
        raise RuntimeError(
            f"无法连接 MySQL ({MYSQL_HOST}:{MYSQL_PORT})，请确认服务已启动: {e}"
        )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def _migrate_character_global() -> None:
    """旧库迁移：characters 由「每档一角色」改为全局唯一女主角设定书。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "characters" not in tables:
        return
    char_columns = {c["name"] for c in inspector.get_columns("characters")}
    if "save_id" not in char_columns:
        return

    logger.info("检测到旧版 characters 结构，开始迁移为全局女主角")
    if "characters_legacy" in tables:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE characters_legacy"))
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE characters RENAME TO characters_legacy"))
        save_columns = {c["name"] for c in inspect(engine).get_columns("saves")}
        if "character_id" not in save_columns:
            conn.execute(text("ALTER TABLE saves ADD COLUMN character_id INT NULL"))

    import orm

    orm.Character.__table__.create(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO characters "
                "(name, age, relation, persona, freeform, created_at, updated_at) "
                "SELECT name, age, relation, persona, freeform, created_at, updated_at "
                "FROM characters_legacy ORDER BY updated_at DESC, id DESC LIMIT 1"
            )
        )
        new_id = conn.execute(
            text("SELECT id FROM characters ORDER BY id LIMIT 1")
        ).scalar()
        conn.execute(
            text("UPDATE saves SET character_id = :cid"), {"cid": new_id}
        )
        fk_exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'saves' "
                "AND COLUMN_NAME = 'character_id' "
                "AND REFERENCED_TABLE_NAME = 'characters'"
            )
        ).scalar()
        if not fk_exists:
            conn.execute(
                text(
                    "ALTER TABLE saves ADD CONSTRAINT fk_saves_character "
                    "FOREIGN KEY (character_id) REFERENCES characters(id) "
                    "ON DELETE SET NULL"
                )
            )
        conn.execute(text("DROP TABLE characters_legacy"))
    logger.info("characters 迁移完成（全局角色 id=%s）", new_id)


def _migrate_attribute_double() -> None:
    """属性数值由 FLOAT 升级为 DOUBLE，避免大数值精度丢失。"""
    from sqlalchemy import text

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME IN ('attribute_defs', 'attribute_values') "
                "AND DATA_TYPE = 'float'"
            )
        ).fetchall()
        for table, column in rows:
            conn.execute(
                text(
                    f"ALTER TABLE `{table}` MODIFY COLUMN `{column}` "
                    "DOUBLE NOT NULL"
                )
            )
            logger.info("已升级 %s.%s 为 DOUBLE", table, column)


def _migrate_user_edited() -> None:
    """为角色书与事件/场景定义补充「用户已修改」标记列（用户改动不再被种子覆盖）。"""
    from sqlalchemy import text

    with engine.begin() as conn:
        tables = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME IN ('characters', 'event_defs', 'scene_defs')"
                )
            ).fetchall()
        ]
        for table in tables:
            exists = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t "
                    "AND COLUMN_NAME = 'user_edited'"
                ),
                {"t": table},
            ).scalar()
            if not exists:
                conn.execute(
                    text(
                        f"ALTER TABLE `{table}` ADD COLUMN `user_edited` "
                        "TINYINT(1) NOT NULL DEFAULT 0"
                    )
                )
                logger.info("已为 %s 添加 user_edited 列", table)


def init_db() -> None:
    """建库 + 建表 + 结构迁移（幂等）。"""
    ensure_database()
    import orm  # noqa: F401  确保模型已注册到 Base.metadata

    Base.metadata.create_all(engine)
    _migrate_character_global()
    _migrate_attribute_double()
    _migrate_user_edited()
    logger.info("数据库 %s 初始化完成", MYSQL_DATABASE)


def get_session():
    """FastAPI 依赖：每请求一个会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
