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


def apply_deltas(
    defs_map: dict[str, AttributeDef],
    values: dict[str, float],
    deltas: dict | None,
    *,
    max_delta: float = ATTR_MAX_DELTA_PER_MESSAGE,
) -> tuple[dict[str, float], list[dict]]:
    """应用 AI 状态标签的属性变化。

    - 只接受已定义、启用且 ai_editable 的属性（金钱等不可被 AI 改动）
    - 单轮变化先钳制到 ±max_delta，再钳制到属性的 [min, max]
    返回 (新值字典, 变化明细列表)。
    """
    new_values = dict(values)
    changes: list[dict] = []
    for key, raw_delta in (deltas or {}).items():
        definition = defs_map.get(key)
        if definition is None or not definition.enabled or not definition.ai_editable:
            continue
        try:
            delta = float(raw_delta)
        except (TypeError, ValueError):
            continue
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
