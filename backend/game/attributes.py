"""
属性数值 — 钳制、状态标签应用与阶段推导（PLAN 5.2 / 5.7）。
"""
from __future__ import annotations

from config import ATTR_MAX_DELTA_PER_MESSAGE
from orm import AttributeDef

PHASES = ("陌生", "熟悉", "亲近", "依恋")
PHASE_KEYS = {
    "陌生": "stranger",
    "熟悉": "familiar",
    "亲近": "close",
    "依恋": "attached",
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def phase_of(values: dict[str, float]) -> str:
    """关系阶段：由好感度/信任/依赖综合推导（简化版，M5 深化）。"""
    score = (
        values.get("affection", 0.0) * 0.5
        + values.get("trust", 0.0) * 0.3
        + values.get("dependence", 0.0) * 0.2
    )
    if score >= 70:
        return PHASES[3]
    if score >= 45:
        return PHASES[2]
    if score >= 20:
        return PHASES[1]
    return PHASES[0]


def phase_key_of(values: dict[str, float]) -> tuple[str, str]:
    """返回 (阶段 key, 阶段中文名)。"""
    label = phase_of(values)
    return PHASE_KEYS.get(label, "stranger"), label


def _apply_values(
    defs_map: dict[str, AttributeDef],
    values: dict[str, float],
    deltas: dict | None,
    *,
    max_delta: float | None,
    respect_ai: bool,
) -> tuple[dict[str, float], list[dict]]:
    """按定义应用属性变化；respect_ai 时跳过 AI 不可改的属性。"""
    new_values = dict(values)
    changes: list[dict] = []
    if not isinstance(deltas, dict):
        return new_values, changes
    for key, raw_delta in deltas.items():
        definition = defs_map.get(key)
        if definition is None or not definition.enabled:
            continue
        if respect_ai and not definition.ai_editable:
            continue
        try:
            delta = float(raw_delta)
        except (TypeError, ValueError):
            continue
        if max_delta is not None:
            delta = clamp(delta, -max_delta, max_delta)
        if delta == 0:
            continue
        old = float(new_values.get(key, definition.default_value))
        new = clamp(old + delta, definition.min, definition.max)
        if new == old:
            continue
        new_values[key] = new
        changes.append({
            "key": key,
            "name": definition.name,
            "old": old,
            "new": new,
            "delta": new - old,
        })
    return new_values, changes


def apply_deltas(
    defs_map: dict[str, AttributeDef],
    values: dict[str, float],
    deltas: dict | None,
    *,
    max_delta: float | None = ATTR_MAX_DELTA_PER_MESSAGE,
) -> tuple[dict[str, float], list[dict]]:
    """应用 AI 状态标签的属性变化（跳过 ai_editable=false 的属性）。"""
    return _apply_values(defs_map, values, deltas, max_delta=max_delta, respect_ai=True)


def apply_effects(
    defs_map: dict[str, AttributeDef],
    values: dict[str, float],
    deltas: dict | None,
    *,
    max_delta: float | None = None,
) -> tuple[dict[str, float], list[dict]]:
    """应用事件/动作效果的属性变化（可改金钱，默认不设单次上限）。"""
    return _apply_values(defs_map, values, deltas, max_delta=max_delta, respect_ai=False)


def apply_ticks(
    defs_map: dict[str, AttributeDef],
    values: dict[str, float],
    game_hours: float,
) -> tuple[dict[str, float], list[dict]]:
    """按游戏小时结算 tick 规则：decay 衰减 / recover 恢复 / regress 回归中值。"""
    if game_hours <= 0:
        return dict(values), []
    new_values = dict(values)
    changes: list[dict] = []
    for key, definition in defs_map.items():
        rule = definition.tick_rule or {}
        if not definition.enabled or not isinstance(rule, dict):
            continue
        mode = str(rule.get("mode") or "").strip()
        old = float(new_values.get(key, definition.default_value))
        new = old
        if mode == "decay":
            amount = float(rule.get("amount_per_hour") or 0.0)
            new = old - amount * game_hours
        elif mode == "recover":
            amount = float(rule.get("amount_per_hour") or 0.0)
            new = old + amount * game_hours
        elif mode == "regress":
            target = float(rule.get("target") or 0.0)
            rate = float(rule.get("rate_per_hour") or 0.0) * game_hours
            new = old + clamp(target - old, -rate, rate)
        else:
            continue
        new = clamp(new, definition.min, definition.max)
        if abs(new - old) < 1e-9:
            continue
        new_values[key] = new
        changes.append({
            "key": key,
            "name": definition.name,
            "old": old,
            "new": new,
            "delta": new - old,
            "source": "tick",
        })
    return new_values, changes
