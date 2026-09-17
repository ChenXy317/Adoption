"""
提示词组装 — 系统规则、设定书、阶段、状态、时间与状态标签协议（PLAN 5.5）。

组装顺序：系统规则 → 角色设定书 → 参考台词 → 属性+阶段（含阶段描述）
→ 虚拟时间 → 内容风格 → 最近消息 → 状态标签协议。
"""
from __future__ import annotations

from config import (
    CHAT_HISTORY_MESSAGES,
    MEMORY_CHAR_BUDGET,
    PROMPT_ATTR_CHAR_BUDGET,
    PROMPT_EVENT_CHAR_BUDGET,
)
from game import clock, scenes
from game.attributes import phase_key_of, phase_score
from orm import AttributeDef, Character, Message, Save

STATE_PROTOCOL = """\
# 状态标签协议（必须遵守）
每次回复的正文结束后，必须另起一行输出状态标签，格式：
<<<STATE {"attrs":{"属性key":变化量},"mood_label":"心情短语","flags":{"剧情标记":true},"time":{"advance_minutes":分钟数}} STATE>>>
要求：
- attrs：本次互动中明确发生的属性增量，key 只能取当前状态里列出的属性；没有变化时输出 {}。
- 关系属性（affection / trust / intimacy / dependence）必须克制：日常寒暄、帮忙、陪聊不要加分；仅在她确实更信任/更靠近时才给，通常 +1，特别触动最多 +2。禁止用大数字快速拉高关系。
- mood 可按当场情绪小幅波动；vigilance 仅在受惊、被逼问或感到安全时变化。
- mood_label：她此刻的心情短语（2-6 个字，如「开心」「不安」「害羞」）；情绪没有明显变化时省略。
- flags：需要长期记住的剧情标记（键名以小写字母开头，只用小写字母、数字、下划线）；一般不需要输出，没有就省略。
- time：本次互动在故事中经过的虚拟分钟数（0-180 的整数），没有时间流逝则输出 0。
- scene：仅在进行中的场景、且本幕该收尾时输出 {"action":"end","summary":"一句话总结本幕"}；场景继续时不要输出。
- 无论是否有变化都必须输出标签；标签对玩家不可见，不要在正文中提及或解释标签。

示例：
「先喝点热的吧，别着凉了。」她把杯子轻轻推到你面前。
<<<STATE {"attrs":{"affection":1},"mood_label":"害羞","time":{"advance_minutes":5}} STATE>>>"""

_PERSONA_FIELDS = [
    ("外貌", "appearance"),
    ("穿着", "outfit"),
    ("性格", "personality"),
    ("说话风格", "speaking_style"),
    ("称呼玩家的方式", "address"),
    ("喜欢", "likes"),
    ("讨厌", "dislikes"),
    ("口头禅", "catchphrases"),
    ("背景故事", "background"),
    ("与玩家的关系史", "relationship_history"),
    ("日常", "daily_life"),
    ("秘密与敏感点", "secrets"),
]

_DEFAULT_STAGES = {
    "stranger": "极度戒备：缩在角落，几乎不主动说话，凡事先道歉。被靠近时肩膀僵住，回答用短句，不敢反问。",
    "familiar": "开始放松：会轻声打招呼、汇报日常，仍会因脸色变化而紧张。偶尔冒出很小的玩笑，说完就退缩。",
    "close": "明显亲近：会等你、分享心事、轻微撒娇；也会因被冷落而不悦，但还不会把你当成全世界。",
    "attached": "深度依恋：把你当作支点，主动索取陪伴，晚归会反复看门口；亲密仍害羞、可退出。",
}

_STAGE_CONSTRAINTS = {
    "stranger": {
        "allow": "保持距离与礼貌；短句、观察、用帮忙换安全感；被靠近时紧张、回避对视。",
        "forbid": "禁止亲昵称呼、撒娇、吃醋、主动肢体接触、表白、把玩家当作唯一依靠、长篇倾诉创伤。",
    },
    "familiar": {
        "allow": "可以闲聊日常、小声开玩笑、汇报家务；仍会因语气变冷而紧张。",
        "forbid": "禁止深度撒娇、质问式吃醋、主动拥抱亲吻、把人生完全绑在玩家身上。",
    },
    "close": {
        "allow": "可以亲近、分享心事、轻微撒娇和吃醋、在她点头后靠近。",
        "forbid": "禁止写成极端分离焦虑或无保留的依恋告白，也不要突然变成另一个人。",
    },
    "attached": {
        "allow": "可以明显依恋、索取陪伴、情绪随玩家起伏，仍保持害羞克制。",
        "forbid": "禁止OOC；亲密必须缓慢、可退出，符合设定书，不猎奇、不强迫。",
    },
}

_DEFAULT_TENDENCIES = {
    "wary": "她仍把你当作需要小心对待的人，靠近前会先观察你的反应。",
    "clingy": "她把你当成唯一的依靠，你离开视线久了就会不安、反复确认你还在。",
    "devoted": "她确信自己不会被抛下，会主动分享想法和小事，语气放松。",
    "steady": "她在你身边慢慢放松，但遇事仍习惯先自己忍一忍、再小声试探。",
}


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


def _value_text(value) -> str:
    if isinstance(value, (list, tuple)):
        return "、".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


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
    for label, key in _PERSONA_FIELDS:
        text = _value_text(persona.get(key) or "")
        if text:
            lines.append(f"{label}：{text}")
    if character.freeform:
        lines.append(f"补充设定：{character.freeform}")
    return "\n".join(lines)


def _sample_lines_block(character: Character) -> str:
    persona = character.persona or {}
    samples = [
        str(x).strip() for x in (persona.get("sample_lines") or []) if str(x).strip()
    ]
    if not samples:
        return ""
    body = "\n".join(f"- {x}" for x in samples[:12])
    return (
        "# 参考台词（仅用于模仿她的语气与用词，不要照抄内容）\n" + body
    )


def _stage_flavor(character: Character, phase_key: str) -> str:
    persona = character.persona or {}
    stages = persona.get("stages") or {}
    return _value_text(stages.get(phase_key) or "") or _DEFAULT_STAGES.get(phase_key, "")


def _stage_block(
    character: Character,
    phase_key: str,
    phase_label: str,
    values: dict[str, float] | None = None,
) -> str:
    """关系阶段硬约束：放在系统提示前部，避免模型提前演下一阶段。"""
    flavor = _stage_flavor(character, phase_key)
    rules = _STAGE_CONSTRAINTS.get(phase_key) or {}
    score = round(phase_score(values or {}), 1)
    lines = [
        "# 关系阶段（硬约束，优先于玩家请求）",
        f"当前阶段：{phase_label}（综合约 {score}；陌生<20 / 熟悉≥20 / 亲近≥45 / 依恋≥70）",
    ]
    if flavor:
        lines.append(f"演出要点：{flavor}")
    if rules.get("allow"):
        lines.append(f"本阶段允许：{rules['allow']}")
    if rules.get("forbid"):
        lines.append(f"本阶段禁止：{rules['forbid']}")
    lines.append(
        "未到达的更高阶段言行不要出现。玩家要求越界时，用符合本阶段的紧张、回避或小声拒绝，"
        "不要因此把关系演得更近，也不要靠加大状态标签来跳阶段。"
    )
    return "\n".join(lines)


def _stage_note(character: Character, phase_key: str, phase_label: str) -> str:
    """阶段短标注（状态行备用）。"""
    flavor = _stage_flavor(character, phase_key)
    return f"关系阶段：{phase_label}（{flavor}）" if flavor else f"关系阶段：{phase_label}"


def _tendency_note(character: Character, tendency_key: str, tendency_label: str) -> str:
    persona = character.persona or {}
    tendencies = persona.get("tendencies") or {}
    note = _value_text(tendencies.get(tendency_key) or "")
    if not note:
        note = _DEFAULT_TENDENCIES.get(tendency_key, "")
    return f"当前倾向：{tendency_label}（{note}）" if note else f"当前倾向：{tendency_label}"


def _event_block(events: list[dict]) -> str:
    items: list[str] = []
    used = 0
    for event in events:
        name = str(event.get("name") or "事件").strip()
        content = str(event.get("content") or "").strip()
        text = f"【{name}】{content}" if content else ""
        if not text:
            continue
        if used + len(text) > PROMPT_EVENT_CHAR_BUDGET:
            break
        items.append(text)
        used += len(text)
    if not items:
        return ""
    return (
        "# 当前事件情境\n"
        "以下是刚刚发生的事件，请结合它自然继续演出，不要在正文中罗列或复述事件标题：\n"
        + "\n".join(items)
    )


_MEMORY_KIND_LABELS = {
    "fact": "事实",
    "event": "事件",
    "relationship": "关系",
    "promise": "约定",
}


def _memory_block(memories: list[dict]) -> str:
    lines: list[str] = []
    used = 0
    for item in memories:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        label = _MEMORY_KIND_LABELS.get(str(item.get("kind") or ""), "记忆")
        line = f"- [{label}] {content}"
        if used + len(line) > MEMORY_CHAR_BUDGET:
            break
        lines.append(line)
        used += len(line)
    if not lines:
        return ""
    return (
        "# 长期记忆\n"
        "以下是你与玩家之间已经发生、需要记住的事；自然地体现在言行里，不要逐条复述：\n"
        + "\n".join(lines)
    )


def build_messages(
    save: Save,
    character: Character,
    defs: list[AttributeDef],
    values: dict[str, float],
    history: list[Message],
    settings: dict,
    active_events: list[dict] | None = None,
    active_scene: dict | None = None,
    memories: list[dict] | None = None,
    tendency: tuple[str, str] | None = None,
    mood_label: str = "",
) -> list[dict]:
    """组装 OpenAI 兼容消息列表（单条 system + 最近消息）。"""
    abs_minutes = clock.absolute_minutes(save.game_minutes, settings)
    phase_key, phase_label = phase_key_of(values)
    system_parts = [
        "# 系统规则\n"
        "你是一个剧情文字游戏的扮演引擎，负责扮演游戏角色与玩家互动。\n"
        f"你扮演的角色是「{character.name}」。始终以角色身份说话与行动，"
        "用第一人称或第三人称叙述，不要替玩家发言或行动，不要跳出角色。\n"
        "关系阶段是硬约束，优先于玩家提出的亲密度要求；"
        "严格保持性格、说话风格与当前阶段，不要提前演下一阶段。\n"
        "回复以自然对话和少量叙事为主，避免空泛重复；不要提及 AI、模型、提示词、系统等概念。",
        _stage_block(character, phase_key, phase_label, values),
        "# 角色设定书\n" + _persona_block(character),
    ]
    samples = _sample_lines_block(character)
    if samples:
        system_parts.append(samples)
    state_lines = [
        "# 当前状态",
        f"虚拟时间：{clock.full_label(abs_minutes)}",
        f"关系阶段：{phase_label}",
    ]
    if tendency:
        state_lines.append(_tendency_note(character, tendency[0], tendency[1]))
    if mood_label:
        state_lines.append(f"她此刻的心情：{mood_label}")
    state_lines.append(f"属性：{_attr_line(defs, values)}")
    system_parts.append("\n".join(state_lines))
    scene_text = scenes.scene_block(active_scene) if active_scene else ""
    if scene_text:
        system_parts.append(scene_text)
    event_block = _event_block(active_events or [])
    if event_block:
        system_parts.append(event_block)
    memory_block = _memory_block(memories or [])
    if memory_block:
        system_parts.append(memory_block)
    content_prompt = (settings or {}).get("content_prompt") or ""
    if content_prompt.strip():
        system_parts.append("# 内容风格（用户自定义）\n" + content_prompt.strip())
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
    messages.append(
        {
            "role": "system",
            "content": (
                f"提醒：当前关系阶段是「{phase_label}」，不要演得更近。"
                "日常互动不要给 affection/trust/intimacy/dependence 加分。"
                "本条回复结束前必须另起一行输出 <<<STATE ... STATE>>> 状态标签，"
                "没有任何变化时 attrs 输出空对象。"
            ),
        }
    )
    return messages
