"""
虚拟时钟 — 分钟换算、时段划分与显示（PLAN 5.4）。

时间与现实完全隔离：game_minutes 为开局后累计分钟，
绝对虚拟分钟 = 起始偏移 + game_minutes；月长固定 30 天。
"""
from __future__ import annotations

from config import CALENDAR_DEFAULT, TIME_DEFAULT_ADVANCE, TIME_MAX_ADVANCE_PER_MESSAGE

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


def day_index(abs_minutes: int) -> int:
    """绝对虚拟分钟所属的日历日序号（自虚拟年 1 月 1 日起算）。"""
    return int(abs_minutes) // DAY_MINUTES


def game_day_of(game_minutes: int, settings: dict | None = None) -> int:
    """开局当天为第 1 天；跨过午夜进入下一天。"""
    base = start_offset(settings)
    return (base + max(0, int(game_minutes))) // DAY_MINUTES - base // DAY_MINUTES + 1


def day_starts_between(from_abs: int, to_abs: int, *, max_days: int = 90) -> list[int]:
    """返回 (from_abs, to_abs] 内每个午夜的绝对分钟，用于跨日判定。"""
    if to_abs <= from_abs:
        return []
    first = (int(from_abs) // DAY_MINUTES + 1) * DAY_MINUTES
    starts: list[int] = []
    moment = first
    while moment <= to_abs and len(starts) < max_days:
        starts.append(moment)
        moment += DAY_MINUTES
    return starts


def period_keys() -> list[str]:
    return [key for _, key, _ in _PERIOD_TABLE]


def advance_limits(settings: dict | None) -> tuple[int, int]:
    """返回 (默认推进分钟, 单条消息最大推进分钟)；存档 settings.advance 可覆盖。"""
    default = int(TIME_DEFAULT_ADVANCE)
    maximum = int(TIME_MAX_ADVANCE_PER_MESSAGE)
    cfg = (settings or {}).get("advance")
    if isinstance(cfg, dict):
        raw_default = cfg.get("default_minutes")
        raw_max = cfg.get("max_per_message")
        try:
            if raw_default is not None:
                default = max(0, int(raw_default))
        except (TypeError, ValueError):
            pass
        try:
            if raw_max is not None:
                maximum = max(1, int(raw_max))
        except (TypeError, ValueError):
            pass
    return default, maximum


def next_period_start(abs_minutes: int, period_key: str) -> int | None:
    """下一个指定时段的开始时刻；当前正处于该时段时跳到次日。"""
    start = {key: begin for begin, key, _ in _PERIOD_TABLE}.get(period_key)
    if start is None:
        return None
    candidate = (int(abs_minutes) // DAY_MINUTES) * DAY_MINUTES + start
    if candidate <= abs_minutes:
        candidate += DAY_MINUTES
    return candidate


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
