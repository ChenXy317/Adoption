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


def init_db() -> None:
    """建库 + 建表（幂等）。"""
    ensure_database()
    import orm  # noqa: F401  确保模型已注册到 Base.metadata

    Base.metadata.create_all(engine)
    logger.info("数据库 %s 初始化完成", MYSQL_DATABASE)


def get_session():
    """FastAPI 依赖：每请求一个会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
