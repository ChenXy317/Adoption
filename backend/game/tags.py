"""
状态标签协议 — 流式剥离 <<<STATE ... STATE>>> 并解析 JSON（PLAN 5.5）。

模型回复末尾可能带一行状态标签，对用户不可见；
标签可能跨多个流式 chunk，需要 hold-back 缓冲，流结束 flush。
"""
from __future__ import annotations

import json
import re

STATE_START = "<<<STATE"
STATE_END = "STATE>>>"
_MAX_TAG_CHARS = 16384


def _hold_len(text: str, marker: str) -> int:
    """返回 text 末尾作为 marker 前缀的最长长度（需要暂缓输出的部分）。"""
    limit = min(len(text), len(marker) - 1)
    for k in range(limit, 0, -1):
        if marker.startswith(text[-k:]):
            return k
    return 0


class StateTagStripper:
    """剥离状态标签：feed 返回可见文本，state_raw 保存标签原文。"""

    def __init__(self) -> None:
        self._buf = ""
        self._in_tag = False
        self.state_raw = ""
        self.tag_found = False

    def feed(self, text: str) -> str:
        if not text:
            return ""
        self._buf += text
        out: list[str] = []
        while self._buf:
            if self._in_tag:
                end = self._buf.find(STATE_END)
                if end == -1:
                    if len(self._buf) > _MAX_TAG_CHARS:
                        out.append(STATE_START + self._buf)
                        self._buf = ""
                        self._in_tag = False
                    break
                self.state_raw = self._buf[:end].strip()
                self.tag_found = True
                self._buf = self._buf[end + len(STATE_END):]
                self._in_tag = False
                continue
            idx = self._buf.find(STATE_START)
            if idx == -1:
                hold = _hold_len(self._buf, STATE_START)
                if hold:
                    out.append(self._buf[:-hold])
                    self._buf = self._buf[-hold:]
                else:
                    out.append(self._buf)
                    self._buf = ""
                break
            out.append(self._buf[:idx])
            self._buf = self._buf[idx + len(STATE_START):]
            self._in_tag = True
        return "".join(out)

    def flush(self) -> str:
        """流结束：未闭合标签视为残留丢弃，其余文本返回。"""
        if self._in_tag:
            self._buf = ""
            self._in_tag = False
            return ""
        text = self._buf
        self._buf = ""
        return text


def parse_state(raw: str | None) -> dict | None:
    """解析标签内 JSON，失败返回 None（静默忽略）。"""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            return None
    return data if isinstance(data, dict) else None
