"""从大模型输出中拆分思考过程与正式回答。"""
from __future__ import annotations

import re

_THINK_TAG_RE = re.compile(
    r"<(?:redacted_)?think(?:ing)?>\s*([\s\S]*?)\s*</(?:redacted_)?think(?:ing)?>",
    re.IGNORECASE,
)


def split_inline_thinking(text: str) -> tuple[str, str]:
    """从 content 中剥离  / <thinking> 标签内容。"""
    thinking_parts: list[str] = []
    rest = text or ""
    while True:
        match = _THINK_TAG_RE.search(rest)
        if not match:
            break
        body = (match.group(1) or "").strip()
        if body:
            thinking_parts.append(body)
        rest = (rest[: match.start()] + rest[match.end() :]).strip()
    thinking = "\n\n".join(thinking_parts).strip()
    return thinking, rest.strip()


def merge_thinking_parts(*parts: str) -> str:
    items = [p.strip() for p in parts if p and p.strip()]
    return "\n\n".join(items)
