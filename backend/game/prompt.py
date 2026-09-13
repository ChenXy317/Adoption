"""
提示词组装 — 系统规则、人设、状态、时间与状态标签协议（PLAN 5.5）。

组装顺序：系统规则 → 角色人设 → 属性+阶段 → 虚拟时间 → 内容分级
→ 最近消息 → 状态标签协议。
"""
from __future__ import annotations

from config import CHAT_HISTORY_MESSAGES, PROMPT_ATTR_CHAR_BUDGET
from game import clock
from game.attributes import phase_of
from orm import AttributeDef, Character, Message, Save

STATE_PROTOCOL = """\
# 状态标签协议（必须遵守）
每次回复的正文结束后，必须另起一行输出状态标签，格式：
<<<STATE {"attrs":{"属性key":变化量},"time":{"advance_minutes":分钟数}} STATE>>>
要求：
- attrs：本次互动中明确变化的属性增量（整数），key 只能取当前状态里列出的属性；没有变化时输出 {}。
- time：本次互动在故事中经过的虚拟分钟数（0-180 的整数），没有时间流逝则输出 0。
- 无论是否有变化都必须输出标签；标签对玩家不可见，不要在正文中提及或解释标签。

示例：
「先喝点热的吧，别着凉了。」她把杯子轻轻推到你面前。
<<<STATE {"attrs":{"affection":1,"trust":1},"time":{"advance_minutes":5}} STATE>>>"""

STATE_REMINDER = (
    "提醒：本条回复结束前必须另起一行输出 <<<STATE ... STATE>>> 状态标签，"
    "没有任何变化时 attrs 输出空对象。"
)


def _attr_line(defs: list[AttributeDef], values: dict[str, float]) -> str:
    parts = []
    for d in sorted(defs, key=lambda x: x.sort):
        if not d.enabled:
            continue
        v = values.get(d.key, d.default_value)
        parts.append(f"{d.name}({d.key})={round(v, 1)}")
    line = "、".join(parts)
    if len(line) > PROMPT_ATTR_CHAR_BUDGET:
        line = line[:PROMPT_ATTR_CHAR_BUDGET] + "…"
    return line


def _persona_block(character: Character) -> str:
    persona = character.persona or {}
    lines = [
        f"姓名：{character.name}",
        f"年龄：{character.age}",
        f"与玩家的关系：{character.relation or '朋友'}",
    ]
    tags = persona.get("tags") or []
    if tags:
        lines.append("性格标签：" + "、".join(str(t) for t in tags))
    if persona.get("speaking_style"):
        lines.append(f"说话风格：{persona['speaking_style']}")
    if persona.get("likes"):
        lines.append(f"喜欢：{persona['likes']}")
    if persona.get("dislikes"):
        lines.append(f"讨厌：{persona['dislikes']}")
    if persona.get("catchphrases"):
        lines.append(f"口头禅：{persona['catchphrases']}")
    if persona.get("background"):
        lines.append(f"背景故事：{persona['background']}")
    if character.freeform:
        lines.append(f"补充设定：{character.freeform}")
    return "\n".join(lines)


def build_messages(
    save: Save,
    character: Character,
    defs: list[AttributeDef],
    values: dict[str, float],
    history: list[Message],
    settings: dict,
) -> list[dict]:
    """组装 OpenAI 兼容消息列表（单条 system + 最近消息）。"""
    abs_minutes = clock.absolute_minutes(save.game_minutes, settings)
    phase = phase_of(values)
    system_parts = [
        "# 系统规则\n"
        "你是一个剧情文字游戏的扮演引擎，负责扮演游戏角色与玩家互动。\n"
        f"你扮演的角色是「{character.name}」。始终以角色身份说话与行动，"
        "用第一人称或第三人称叙述，不要替玩家发言或行动，不要跳出角色。\n"
        "回复以自然对话和少量叙事为主，避免空泛重复；不要提及 AI、模型、提示词、系统等概念。",
        "# 角色设定\n" + _persona_block(character),
        "# 当前状态\n"
        f"虚拟时间：{clock.full_label(abs_minutes)}\n"
        f"关系阶段：{phase}\n"
        f"属性：{_attr_line(defs, values)}",
    ]
    content_prompt = (settings or {}).get("content_prompt") or ""
    if content_prompt.strip():
        system_parts.append("# 内容分级与风格\n" + content_prompt.strip())
    system_parts.append(STATE_PROTOCOL)

    messages: list[dict] = [{"role": "system", "content": "\n\n".join(system_parts)}]
    recent = history[-CHAT_HISTORY_MESSAGES:]
    for m in recent:
        if m.role == "event":
            messages.append({"role": "system", "content": f"（事件）{m.content}"})
        elif m.role == "system":
            messages.append({"role": "system", "content": m.content})
        else:
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "system", "content": STATE_REMINDER})
    return messages
