"""
全局配置 — 路径、数据库、模型调用与游戏默认参数。

数据库密码通过环境变量 MYSQL_PASSWORD 提供（可写在项目根 .env）。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
SEEDS_DIR = BASE_DIR / "seeds"

load_dotenv(PROJECT_DIR / ".env")

# 无鉴权 OpenAI 兼容端点（如本地 Ollama）时客户端仍需占位 key
DUMMY_API_KEY = "sk-no-auth"
DEFAULT_MAX_TOKENS = 8192

# ── 服务监听 ──
APP_HOST = os.environ.get("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
try:
    APP_PORT = int(os.environ.get("APP_PORT", "18730"))
except (ValueError, TypeError):
    raise RuntimeError("APP_PORT 环境变量值无效，应为整数端口号")

# CORS 允许来源（开发时 Vite 直连后端）
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ── MySQL ──
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
try:
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
except (ValueError, TypeError):
    raise RuntimeError("MYSQL_PORT 环境变量值无效，应为整数端口号")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "new_idea")
MYSQL_CHARSET = "utf8mb4"

# ── 生成参数（创建存档时预填，存档 settings 可覆盖）──
DEFAULT_PARAMS = {
    "temperature": 1.0,
    "top_p": 0.95,
    "presence_penalty": 0.3,
    "frequency_penalty": 0.0,
    "num_predict": 2048,
}

# ── 虚拟时间（详见 PLAN 5.4）──
TIME_DEFAULT_ADVANCE = 10          # AI 未输出推进量时的兜底（分钟）
TIME_MAX_ADVANCE_PER_MESSAGE = 180  # 单条回复允许的最大推进（分钟）
TIME_MAX_JUMP_HOURS = 24           # 单次显式动作/事件推进上限（小时）
CALENDAR_DEFAULT = {"month": 5, "day": 1, "hour": 8, "minute": 0}

# ── 属性 ──
ATTR_MAX_DELTA_PER_MESSAGE = 20  # 单轮状态标签对单个属性的变化上限

# ── 事件（详见 PLAN 5.3）──
EVENT_MAX_PER_SETTLEMENT = 3       # 单次结算最多注入的事件数
EVENT_RECENT_WINDOW_MINUTES = 180  # 事件情境注入 prompt 的有效窗口（虚拟分钟）

# ── 多轮场景（详见 PLAN 5.3）──
SCENE_PROMPT_CHAR_BUDGET = 600     # 场景设定注入 prompt 的字符预算
SCENE_MEMORY_IMPORTANCE = 7        # 场景结束写入记忆的默认重要度（1-10）

# ── 经济与冷落（M5 启用；数值已于 PLAN §10 定稿）──
WORK_HOURS = 4                     # 打工耗时（虚拟小时）
WORK_PAY = 120                     # 打工收益（金钱），时薪 30
GIFT_TIERS = {                     # 礼物档位参考价（M5 礼物清单按此定价）
    "small": {"price": 80, "affection": 2},
    "large": {"price": 300, "affection": 5},
}
NEGLECT_DAYS = 3                   # 两次互动间推进 ≥N 游戏日且无对话视为冷落
NEGLECT_AFFECTION_PER_DAY = 1      # 冷落每多 1 游戏日的好感降幅
NEGLECT_AFFECTION_MAX = 5          # 单次冷落的好感降幅上限

# ── 对话与记忆（详见 PLAN 5.6）──
CHAT_HISTORY_MESSAGES = 30      # 组装 prompt 的最近消息条数
MEMORY_TRIGGER_TURNS = 20       # 未总结消息达到该数量触发总结
MEMORY_IDLE_MINUTES = 30        # 空闲调度（技术性，非虚拟时间；暂未启用）
MEMORY_CHAR_BUDGET = 2000       # 永久记忆注入 prompt 的字符预算
MEMORY_MODEL = ""               # 总结模型 key；空则用主对话模型
MEMORY_MAX_MESSAGES_PER_JOB = 200   # 单次总结最多处理的消息条数
MEMORY_SUMMARY_MAX_TOKENS = 2048    # 总结请求的输出上限
MEMORY_PROMPT_CHAR_BUDGET = 12000   # 总结请求中对话/事件原文的字符预算
MEMORY_EXISTING_LIMIT = 60          # 总结时附上的已有记忆条数

# 各 prompt 块字符预算
PROMPT_ATTR_CHAR_BUDGET = 600
PROMPT_EVENT_CHAR_BUDGET = 800
SCENE_MAX_TURNS_DEFAULT = 12
