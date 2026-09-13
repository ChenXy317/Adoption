"""
虚拟时钟 — 分钟换算、时段划分与显示（PLAN 5.4）。

时间与现实完全隔离：game_minutes 为开局后累计分钟，
绝对虚拟分钟 = 起始偏移 + game_minutes；月长固定 30 天。
"""
from __future__ import annotations

from config import CALENDAR_DEFAULT

DAY_MINUTES = 1440
MONTH_DAYS = 30
MONTH_MINUTES = DAY_MINUTES * MONTH_DAYS
YEAR_MONTHS = 12
YEAR_MINUTES = MONTH_MINUTES * YEAR_MONTHS

# (起始分钟, key, 名称)，按日内顺序排列；22:00 后归入深夜
_PERIOD_TABLE = [
    (5 * 60, "dawn", "清晨"),
    (8 * 60, "morning", "上午"),
    (11 * 60, "noon", "中午"),
    (13 * 60, "afternoon", "下午"),
    (17 * 60, "evening", "傍晚"),
    (19 * 60, "night", "晚上"),
    (22 * 60, "late_night", "深夜"),
]


def start_offset(settings: dict | None) -> int:
    """起始日期（虚拟年内偏移分钟），可在存档 settings.calendar 中配置。"""
    cal = dict(CALENDAR_DEFAULT)
    raw = (settings or {}).get("calendar") or {}
    for key in cal:
        value = raw.get(key)
        if isinstance(value, (int, float)):
            cal[key] = int(value)
    return (
        (cal["month"] - 1) * MONTH_MINUTES
        + (cal["day"] - 1) * DAY_MINUTES
        + cal["hour"] * 60
        + cal["minute"]
    )


def absolute_minutes(game_minutes: int, settings: dict | None) -> int:
    return start_offset(settings) + int(game_minutes)


def period_of(minute_of_day: int) -> tuple[str, str]:
    """日内分钟 → (时段 key, 时段名)。"""
    m = minute_of_day % DAY_MINUTES
    current = ("late_night", "深夜")
    for start, key, name in _PERIOD_TABLE:
        if m >= start:
            current = (key, name)
    return current


def split(abs_minutes: int) -> dict:
    """绝对虚拟分钟 → 月/日/时/分/时段。"""
    m = abs_minutes % YEAR_MINUTES
    day_index, minute_of_day = divmod(m, DAY_MINUTES)
    month_index, day = divmod(day_index, MONTH_DAYS)
    hour, minute = divmod(minute_of_day, 60)
    period_key, period_name = period_of(minute_of_day)
    return {
        "month": month_index + 1,
        "day": day + 1,
        "hour": hour,
        "minute": minute,
        "period_key": period_key,
        "period_name": period_name,
    }


def date_label(abs_minutes: int) -> str:
    d = split(abs_minutes)
    return f"{d['month']} 月 {d['day']} 日"


def time_label(abs_minutes: int) -> str:
    d = split(abs_minutes)
    return f"{d['month']} 月 {d['day']} 日 · {d['period_name']}"


def full_label(abs_minutes: int) -> str:
    d = split(abs_minutes)
    return (
        f"{d['month']} 月 {d['day']} 日 · {d['period_name']} "
        f"{d['hour']:02d}:{d['minute']:02d}"
    )
