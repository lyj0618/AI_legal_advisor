"""法规时效性规则检测（不依赖外部法规库）。"""
from __future__ import annotations

import re
from typing import Any

_REPEALED = re.compile(
    r"(已废止|同时废止|本法自.*?起废止|自本公告发布之日起废止|不再施行|停止执行)",
    re.IGNORECASE,
)
_SUPERSEDED = re.compile(r"(已被.*?修改|同时修改|对.*?有关条文作如下修改|修正案)", re.IGNORECASE)
_EFFECTIVE = re.compile(
    r"(自\s*\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*起施行|"
    r"自\s*\d{4}-\d{1,2}-\d{1,2}\s*起施行|"
    r"本法自公布之日起施行)",
)
_EXPIRED_HINT = re.compile(r"(失效|届满|有效期至|执行期满)", re.IGNORECASE)


def analyze_legal_timeliness(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        return {"level": "unknown", "warnings": [], "hints": []}

    warnings: list[str] = []
    hints: list[str] = []

    for m in _REPEALED.finditer(text):
        snippet = text[max(0, m.start() - 20) : m.end() + 40].replace("\n", " ")
        warnings.append(f"疑似废止表述：…{snippet}…")

    for m in _SUPERSEDED.finditer(text):
        snippet = text[max(0, m.start() - 20) : m.end() + 40].replace("\n", " ")
        hints.append(f"疑似已被修订：…{snippet}…")

    for m in _EFFECTIVE.finditer(text):
        snippet = text[max(0, m.start() - 10) : m.end() + 20].replace("\n", " ")
        hints.append(f"施行/生效信息：{snippet}")

    for m in _EXPIRED_HINT.finditer(text):
        snippet = text[max(0, m.start() - 20) : m.end() + 40].replace("\n", " ")
        warnings.append(f"疑似失效/期限表述：…{snippet}…")

    level = "ok"
    if warnings:
        level = "warning"
    elif hints:
        level = "info"

    return {
        "level": level,
        "warnings": warnings[:8],
        "hints": hints[:8],
        "warning_count": len(warnings),
        "hint_count": len(hints),
    }
