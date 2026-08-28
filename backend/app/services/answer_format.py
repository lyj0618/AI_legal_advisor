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
_SENTENCE_END_RE = re.compile(r"[。；.;!?！？]")

ANSWER_FORMAT_INSTRUCTION = """

【回答版式】必须严格按下列结构输出。每个一级标题单独占一行，标题下空一行写正文；禁止使用 Markdown 符号。

重要规则：
1. 「结论」必须按下面五段式结构输出，分别说明：问题现象、问题定位、问题自查、解决方案、仍未解决。
   如果某一段确实无内容，可写“无”，但五段标题必须全部保留、顺序不得调换。
2. 「依据」详细说明理由与知识库来源，可分 1. 2. 3. 条陈述；不得与「结论」中的五段内容完全重复。
3. 不得输出「回答依据出处」标题及其正文，该节由系统自动填写。
4. 结论内的二级标题（问题现象、问题定位、问题自查、解决方案、仍未解决）不要加粗、不要用 Markdown，单独占一行即可。

结论

问题现象
（描述用户看到的报错或异常现象）

问题定位
（指出问题产生的根本原因或触发条件）

问题自查
（列出用户可自行检查的步骤，1. 2. 3.）

解决方案
（给出具体可执行的操作步骤，1. 2. 3.）

仍未解决
（若上述步骤无法解决，说明需要进一步提供的信息或反馈渠道；若无疑似未解决项，写“无”）

依据
（说明理由与依据，可引用知识库来源并分 1. 2. 3. 条陈述）

注意事项
（仅当存在风险、例外、合规提醒或操作限制时输出本节；若无则整节省略，不要写「注意事项」标题）

回答依据出处
（本节由系统自动填写，你不得输出「回答依据出处」标题及其正文）

兜底回复
（仅当知识库不足以完整回答、需补充通用性说明时输出；若已能充分作答则整节省略）

【参考示例】当用户问“新建项目时系统提示项目角色都要选人员”时，「结论」必须按如下五段输出：

结论

问题现象
新建项目保存时，系统提示“请确保当前展示的项目角色都已选择人员”。

问题定位
项目建模时必填的角色成员未选择人员；除“其他”外，所有角色成员均为必填项。

问题自查
1. 切换到项目成员标签页，检查各角色是否已分配人员。
2. 确认是否漏选了某个必填角色。

解决方案
1. 在项目成员标签页为每个必填角色选择对应人员。
2. 补全后重新保存项目即可通过校验。

仍未解决
若已补全所有必填角色仍报错，请截图联系系统管理员排查。
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


def _first_sentence(text: str, max_len: int = 80) -> str:
    """取文本第一句（按中文/英文句号、分号等），限制最大长度。"""
    t = (text or "").strip()
    if not t:
        return ""
    m = _SENTENCE_END_RE.search(t)
    if m:
        s = t[: m.end()].strip()
    else:
        s = t
    if len(s) > max_len:
        s = s[:max_len].rstrip() + "…"
    return s


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
            first = _first_sentence(out["依据"], max_len=80)
            out["结论"] = first if first else "请参见下方依据说明。"
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
