"""
知识库文档文本清洗：去 HTML/噪声/冗余后再切片。
"""
from __future__ import annotations

import re
import unicodedata
from html import unescape

# 默认清洗选项（可在知识库 parser_config.clean_options 中覆盖）
DEFAULT_CLEAN_OPTIONS = {
    "enabled": True,
    "remove_noise": True,
    "remove_format": True,
    "process_tables": True,
    "remove_redundant": True,
    "normalize_chars": True,
}


def clean_document_text(raw: str, options: dict | None = None) -> str:
    opts = {**DEFAULT_CLEAN_OPTIONS, **(options or {})}
    if not opts.get("enabled", True):
        return (raw or "").strip()

    text = raw or ""
    if opts.get("remove_format", True):
        text = _html_to_plain(text)
    if opts.get("normalize_chars", True):
        text = _normalize_characters(text)
    if opts.get("remove_noise", True):
        text = _remove_watermarks(text)
        text = _remove_headers_footers(text)
        text = _remove_table_of_contents(text)
        text = _trim_appendix_boilerplate(text)
    if opts.get("process_tables", True):
        text = _format_markdown_tables(text)
    if opts.get("remove_redundant", True):
        text = _remove_obsolete_markers(text)
        text = _deduplicate_paragraphs(text)

    from app.services.chunking import prepare_legal_text

    text = prepare_legal_text(_final_tidy(text))
    return text


def _html_to_plain(text: str) -> str:
    if not text:
        return ""
    if "<" in text and ">" in text:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            for tag in soup(["script", "style", "head", "meta", "link", "noscript"]):
                tag.decompose()
            for table in soup.find_all("table"):
                table.replace_with(_soup_table_to_text(table))
            for br in soup.find_all("br"):
                br.replace_with("\n")
            plain = soup.get_text("\n")
            plain = re.sub(r"\n{3,}", "\n\n", plain)
            plain = re.sub(r"[ \t\u00a0]+", " ", plain)
            return unescape(plain)
        except ImportError:
            text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", text, flags=re.I)
            text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.I)
            text = re.sub(r"<[^>]+>", "\n", text)
            return unescape(text)
    # Markdown 残留
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    return unescape(text)


def _soup_table_to_text(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return _rows_to_structured_text(rows)


def _format_markdown_tables(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i + 1]):
            block = [line]
            i += 1
            while i < len(lines) and "|" in lines[i]:
                block.append(lines[i])
                i += 1
            rows = []
            for bl in block:
                if re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", bl):
                    continue
                cells = [c.strip() for c in bl.strip("|").split("|")]
                if any(cells):
                    rows.append(cells)
            converted = _rows_to_structured_text(rows)
            if converted:
                out.append(converted)
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _rows_to_structured_text(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    if len(rows) == 1:
        return "；".join(rows[0])

    header = rows[0]
    body = rows[1:]
    # 两列表格：键值描述
    if len(header) == 2 and all(len(r) >= 2 for r in body):
        parts = []
        for row in body:
            k, v = row[0].strip(), row[1].strip()
            if k and v:
                parts.append(f"{k}：{v}")
        if parts:
            return "\n".join(parts)

    # 多列：首行作表头
    parts = []
    for row in body:
        cells = [c.strip() for c in row if c.strip()]
        if not cells:
            continue
        if len(header) == len(cells):
            seg = "，".join(f"{header[j]}={cells[j]}" for j in range(len(cells)) if cells[j])
            parts.append(seg)
        else:
            parts.append("，".join(cells))
    return "\n".join(parts)


def _normalize_characters(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffd]", "", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    return text


def _remove_watermarks(text: str) -> str:
    patterns = [
        r"^\s*第\s*\d+\s*页\s*[/／]\s*共\s*\d+\s*页\s*$",
        r"^\s*[-—]?\s*\d+\s*[-—]?\s*$",
        r"^\s*仅供.{0,30}使用\s*$",
        r"^\s*内部资料.{0,20}请勿外传\s*$",
        r"^\s*版权所有.{0,40}$",
        r"^\s*CONFIDENTIAL\s*$",
    ]
    lines = text.split("\n")
    kept = []
    for line in lines:
        s = line.strip()
        if not s:
            kept.append("")
            continue
        if any(re.search(p, s, re.I) for p in patterns):
            continue
        kept.append(line)
    return "\n".join(kept)


def _remove_headers_footers(text: str) -> str:
    lines = [ln.rstrip() for ln in text.split("\n")]
    if len(lines) < 6:
        return text
    freq: dict[str, int] = {}
    for ln in lines:
        s = ln.strip()
        if 4 <= len(s) <= 80:
            freq[s] = freq.get(s, 0) + 1
    repeated = {s for s, c in freq.items() if c >= 3}
    if not repeated:
        return text
    return "\n".join(ln for ln in lines if ln.strip() not in repeated)


def _remove_table_of_contents(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    in_toc = False
    toc_started = False

    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r"^(目录|目\s*录|CONTENTS)\s*$", s, re.I):
            in_toc = True
            toc_started = True
            continue
        if in_toc:
            if not s:
                if toc_started and i > 0 and out:
                    in_toc = False
                continue
            if re.search(r"\.{4,}|…{2,}|·{4,}", s):
                continue
            if re.match(r"^第[一二三四五六七八九十百千\d]+[章节篇]", s):
                in_toc = False
                out.append(line)
                continue
            if re.match(r"^\d+(\.\d+)*\s+\S", s) and len(s) < 60:
                continue
            in_toc = False
        out.append(line)
    return "\n".join(out)


def _trim_appendix_boilerplate(text: str) -> str:
    """保留附录正文，弱化纯索引式条目块。"""
    parts = re.split(r"\n(?=\s*附录\s*[一二三四五六七八九十\d]*\s*[:：]?\s*\n)", text)
    if len(parts) <= 1:
        return _drop_reference_index_block(text)

    main = parts[0]
    appendix_blocks = parts[1:]
    cleaned_appendix = []
    for block in appendix_blocks:
        lines = block.split("\n")
        kept = []
        for line in lines:
            s = line.strip()
            if re.match(r"^参考文献\s*$|^引用文献\s*$", s):
                break
            if re.match(r"^\[\d+\]\s*$", s):
                continue
            kept.append(line)
        if kept:
            cleaned_appendix.append("\n".join(kept))
    return main + ("\n\n" + "\n\n".join(cleaned_appendix) if cleaned_appendix else "")


def _drop_reference_index_block(text: str) -> str:
    lines = text.split("\n")
    cut = len(lines)
    for i, line in enumerate(lines):
        if re.match(r"^(参考文献|引用文献|Bibliography)\s*$", line.strip(), re.I):
            cut = i
            break
    return "\n".join(lines[:cut])


def _remove_obsolete_markers(text: str) -> str:
    text = re.sub(r"（\s*已废止\s*）|\(\s*已废止\s*\)", "", text)
    text = re.sub(r"（\s*失效\s*）|\(\s*失效\s*\)", "", text)
    text = re.sub(r"【\s*旧版\s*】", "", text)
    return text


def _deduplicate_paragraphs(text: str) -> str:
    paras = re.split(r"\n{2,}", text)
    seen: set[str] = set()
    out: list[str] = []
    for p in paras:
        key = re.sub(r"\s+", "", p.strip())[:500]
        if not key or len(key) < 8:
            if p.strip():
                out.append(p.strip())
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(p.strip())
    return "\n\n".join(out)


def _final_tidy(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln.strip() for ln in text.split("\n")]
    merged: list[str] = []
    for ln in lines:
        if not ln:
            if merged and merged[-1] != "":
                merged.append("")
            continue
        merged.append(ln)
    return "\n".join(merged).strip()
