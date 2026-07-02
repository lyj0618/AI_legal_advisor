"""助手回答固定版式：结论 / 依据 / 注意事项 / 回答依据出处 / 兜底回复。"""
from __future__ import annotations

import re

from app.utils import strip_markdown

SECTION_TITLES = ("结论", "依据", "注意事项", "回答依据出处", "兜底回复")
_SECTION_RE = re.compile(
    r"^(" + "|".join(re.escape(t) for t in SECTION_TITLES) + r")\s*$",
    re.MULTILINE,
)
_LEGACY_SUFFIX_RE = re.compile(
    r"(?:\n*---\s*)?\n回答依据出处\s*\n[\s\S]*$",
    re.MULTILINE,
)
_PLACEHOLDER_LINE_RE = re.compile(r"^[（(][^）)]*[）)]\s*$")

ANSWER_FORMAT_INSTRUCTION = """

【回答版式】必须严格按下列结构输出。每个标题单独占一行，标题下空一行写正文；禁止使用 Markdown 符号。

重要：「结论」「依据」两节必须填写实质内容，不得留空、不得只重复标题，不得照抄本说明中的括号提示语。

结论
（用一两句话给出直接、可执行的结论）

依据
（说明理由与依据，可分 1. 2. 3. 条陈述）

注意事项
（仅当存在风险、例外、合规提醒或操作限制时输出本节；若无则整节省略，不要写「注意事项」标题）

回答依据出处
（本节由系统自动填写，你不得输出「回答依据出处」标题及其正文）

兜底回复
（仅当知识库不足以完整回答、需补充通用性说明时输出；若已能充分作答则整节省略）
"""


def parse_answer_sections(text: str) -> dict[str, str]:
    raw = (text or "").strip()
    if not raw:
        return {}
    parts = _SECTION_RE.split(raw)
    if len(parts) <= 1:
        return {"结论": raw}
    sections: dict[str, str] = {}
    i = 1
    while i < len(parts):
        title = parts[i].strip()
        body = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        if title in SECTION_TITLES:
            sections[title] = body
        i += 2
    return sections


def _is_empty_placeholder(text: str) -> bool:
    t = text.strip().lower()
    return t in ("无", "暂无", "无。", "暂无。", "不适用", "—", "-", "n/a", "none") or len(t) <= 2


def _is_instruction_placeholder(body: str) -> bool:
    t = (body or "").strip()
    if not t:
        return True
    if _PLACEHOLDER_LINE_RE.match(t):
        return True
    return _is_empty_placeholder(t)


def _clean_section_body(body: str) -> str:
    body = (body or "").strip()
    if _is_instruction_placeholder(body):
        return ""
    return body


def _sanitize_llm_text(text: str) -> str:
    """去掉模型自行输出的出处节及旧版 --- 出处后缀，避免与系统出处重复。"""
    s = (text or "").strip()
    s = _LEGACY_SUFFIX_RE.sub("", s).strip()
    while True:
        m = re.search(r"^回答依据出处\s*$", s, re.MULTILINE)
        if not m:
            break
        start = m.start()
        rest = s[m.end() :]
        nxt = _SECTION_RE.search(rest)
        end = m.end() + (nxt.start() if nxt else len(rest))
        s = (s[:start] + s[end:]).strip()
    return s


def _sources_indicate_low_relevance(sources_body: str) -> bool:
    t = sources_body or ""
    markers = (
        "未发现与您问题",
        "相关度偏低",
        "未检索到与您问题",
        "最高相关度约为",
        "未在知识库中检索到",
    )
    return any(m in t for m in markers)


def _ensure_core_sections(sections: dict[str, str], raw_text: str, sources_body: str) -> dict[str, str]:
    out = dict(sections)

    if not out and raw_text.strip() and not _only_section_headers(raw_text):
        out["结论"] = raw_text.strip()

    for key in ("结论", "依据", "注意事项", "兜底回复"):
        if key in out:
            cleaned = _clean_section_body(out[key])
            if cleaned:
                out[key] = cleaned
            else:
                out.pop(key, None)

    if not out.get("结论"):
        if out.get("依据"):
            first = out["依据"].split("\n")[0].strip()
            out["结论"] = first[:300] if first else "请参见下方依据说明。"
        elif _sources_indicate_low_relevance(sources_body):
            out["结论"] = "知识库中暂未检索到与您问题直接相关的制度条款，无法给出确定性操作结论。"
        elif (sources_body or "").strip():
            out["结论"] = "已根据知识库检索结果整理参考意见，具体执行请以本单位现行制度或主管部门答复为准。"
        else:
            out["结论"] = "本次未能生成完整回答，请尝试重新表述问题或稍后重试。"

    if not out.get("依据"):
        if _sources_indicate_low_relevance(sources_body):
            out["依据"] = (
                "系统已在绑定知识库中检索，但匹配片段与当前问题的相关度较低，"
                "不宜作为直接依据；建议向人事或行政部门核实午餐津贴等福利制度的最新规定。"
            )
        elif (sources_body or "").strip():
            out["依据"] = "以下整理自知识库检索片段与问题分析，请结合出处列表核对原文。"
        else:
            out["依据"] = "以上结论基于模型分析生成，未绑定或未命中知识库，仅供参考。"

    return out


def _only_section_headers(text: str) -> bool:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return True
    return all(ln in SECTION_TITLES or _PLACEHOLDER_LINE_RE.match(ln) for ln in lines)


def compose_answer(llm_text: str, sources_body: str = "") -> str:
    """合并模型输出与系统生成的「回答依据出处」。"""
    raw = _sanitize_llm_text(strip_markdown((llm_text or "").rstrip()))
    sections = parse_answer_sections(raw)
    sections.pop("回答依据出处", None)
    sections = _ensure_core_sections(sections, raw, sources_body)

    blocks: list[str] = []
    for title in SECTION_TITLES:
        if title == "回答依据出处":
            body = (sources_body or "").strip()
            if body:
                blocks.append(f"{title}\n{body}")
            continue
        body = (sections.get(title) or "").strip()
        if not body:
            continue
        if title in ("注意事项", "兜底回复") and _is_empty_placeholder(body):
            continue
        blocks.append(f"{title}\n{body}")

    return "\n\n".join(blocks)
