"""
FastAPI 服务入口 — 网页版 AI 养成游戏。

负责初始化数据库、注册路由并托管前端静态文件。
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ai_client import ai
from config import ALLOWED_ORIGINS, APP_HOST, APP_PORT, BASE_DIR, FRONTEND_DIR
from db import SessionLocal, init_db
from game import memory
from routes.advance import router as advance_router
from routes.backup import router as backup_router
from routes.catalog import router as catalog_router
from routes.character import router as character_router
from routes.chat import router as chat_router
from routes.defs import router as defs_router
from routes.events import router as events_router
from routes.memories import router as memories_router
from routes.saves import router as saves_router
from routes.scenes import router as scenes_router
from routes.state import router as state_router
from seeds.loader import (
    apply_character_seed,
    apply_event_seeds,
    apply_scene_seeds,
    apply_seeds,
)

def _setup_logging() -> None:
    """日志始终写文件（5MB × 3 轮转）；有控制台（非 pythonw）时同时输出到 stderr。"""
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            BASE_DIR / "server.log",
            encoding="utf-8",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )


_setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if APP_HOST not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "APP_HOST=%s 不是本机回环地址：服务无登录鉴权，请勿暴露到不受信任的网络",
            APP_HOST,
        )
    init_db()
    session = SessionLocal()
    try:
        apply_seeds(session)
        apply_character_seed(session)
        apply_event_seeds(session)
        apply_scene_seeds(session)
        pending_saves = memory.requeue_interrupted(session)
    finally:
        session.close()
    for save_id in pending_saves:
        asyncio.create_task(memory.safe_run_summary(save_id))
        logger.info("补跑中断的记忆总结任务: save=%s", save_id)
    logger.info("服务初始化完成")
    yield
    await ai.close()
    logger.info("服务已关闭")


app = FastAPI(title="AI 养成游戏", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(character_router)
app.include_router(saves_router)
app.include_router(backup_router)
app.include_router(chat_router)
app.include_router(state_router)
app.include_router(defs_router)
app.include_router(catalog_router)
app.include_router(advance_router)
app.include_router(events_router)
app.include_router(scenes_router)
app.include_router(memories_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": "error", "message": str(exc.detail), "detail": ""},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """请求参数错误也返回统一的错误结构（前端 api 客户端依赖 message 字段）。"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(
        str(item) for item in first.get("loc", []) if item not in ("body", "query", "path")
    )
    message = str(first.get("msg") or "参数不合法")
    text = f"{loc}：{message}" if loc else message
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": f"请求参数不合法（{text}）",
            "detail": "",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "服务器内部错误",
            "detail": "",
        },
    )


dist_dir = FRONTEND_DIR / "dist"
if dist_dir.is_dir() and any(dist_dir.iterdir()):
    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    logger.info("已挂载前端静态文件: %s", dist_dir)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "接口不存在", "detail": ""},
            )
        dist_root = dist_dir.resolve()
        candidate = (dist_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
            return FileResponse(candidate)
        return FileResponse(dist_dir / "index.html")
else:
    logger.info("未找到 frontend/dist，开发时请使用 Vite（默认 5173）")


if __name__ == "__main__":
    import uvicorn

    reload_enabled = os.environ.get("UVICORN_RELOAD", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=reload_enabled,
        log_config=None,
    )
