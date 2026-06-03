import importlib
import re
from pathlib import Path

# 法条切片逻辑版本（/health 与分块结果校验用）
CHUNKING_VERSION = "legal-article-v4"

# 法条编号（第X条）
_ARTICLE_NUM = r"第[一二三四五六七八九十百千万零壹贰叁肆伍陆柒捌玖拾佰仟\d]+条"
_LEGAL_ARTICLE_DETECT = re.compile(_ARTICLE_NUM)
_ARTICLE_LINE = re.compile(rf"^(?P<num>{_ARTICLE_NUM})\s*$", re.MULTILINE)
_ARTICLE_LINE_INLINE = re.compile(
    rf"^(?P<num>{_ARTICLE_NUM})\s+[\u4e00-\u9fff]",
    re.MULTILINE,
)
_STRUCT_LINE = re.compile(
    r"^第[一二三四五六七八九十百千万零壹贰叁肆伍陆柒捌玖拾佰仟\d]+[编章节]\s*$"
)
_PUNCT_ONLY = re.compile(r"^[,，、.;；…—\-]+$")
_CN_NUM = r"[一二三四五六七八九十百千万\d]+"


def extract_text(file_path: Path, name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in (".txt", ".md", ".markdown", ".csv"):
        return file_path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise ValueError(f"PDF 解析失败: {e}") from e
    if suffix in (".docx", ".doc"):
        return _extract_word(file_path, suffix)
    raise ValueError(f"暂不支持该文件类型: {suffix}，支持 txt/md/pdf/docx")


def _extract_word(file_path: Path, suffix: str) -> str:
    if suffix == ".docx":
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(str(file_path))
            parts: list[str] = []
            for para in doc.paragraphs:
                text = (para.text or "").strip()
                if text:
                    parts.append(text)
            for table in doc.tables:
                for row in table.rows:
                    cells = [(cell.text or "").strip() for cell in row.cells]
                    line = " | ".join(c for c in cells if c)
                    if line:
                        parts.append(line)
            content = "\n".join(parts).strip()
            if not content:
                raise ValueError("Word 文档无有效文本内容")
            return content
        except ImportError as e:
            raise ValueError("未安装 python-docx，请执行 pip install python-docx") from e
        except Exception as e:
            raise ValueError(f"Word(.docx) 解析失败: {e}") from e

    raise ValueError("旧版 .doc 格式请另存为 .docx 后上传")


def collapse_vertical_legal_headers(text: str) -> str:
    """合并 PDF 竖排断行：第\\n一\\n条 → 第一条。"""
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s == "第" and i + 2 < len(lines):
            mid = lines[i + 1].strip()
            end = lines[i + 2].strip()
            if re.fullmatch(_CN_NUM, mid) and end in ("条", "编", "章", "节"):
                out.append(f"第{mid}{end}")
                i += 3
                continue
        out.append(s)
        i += 1
    merged = "\n".join(out)
    merged = re.sub(
        rf"第\s*({_CN_NUM})\s*条",
        r"第\1条",
        merged,
    )
    return merged


def _is_pdf_broken_layout(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 80:
        return False
    avg_len = sum(len(ln) for ln in lines) / len(lines)
    short = sum(1 for ln in lines if len(ln) <= 2)
    return avg_len < 22 or short > len(lines) * 0.25


def reflow_pdf_legal_text(text: str) -> str:
    """合并 PDF 逐行抽取的断行。"""
    if not text:
        return text
    text = collapse_vertical_legal_headers(text)
    if not _is_pdf_broken_layout(text):
        return text

    lines = text.split("\n")
    out: list[str] = []
    buf: list[str] = []

    def flush_buf() -> None:
        if buf:
            out.append("".join(buf))
            buf.clear()

    for raw in lines:
        s = raw.strip()
        if not s:
            flush_buf()
            if out and out[-1] != "":
                out.append("")
            continue
        s = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", s)
        if _PUNCT_ONLY.match(s):
            if buf:
                buf[-1] += s
            continue
        if _STRUCT_LINE.match(s) or _ARTICLE_LINE.match(s):
            flush_buf()
            out.append(s)
        elif _ARTICLE_LINE_INLINE.match(s):
            flush_buf()
            out.append(s)
        else:
            buf.append(s)
    flush_buf()
    return "\n".join(out).strip()


def _trim_toc_before_body(text: str) -> str:
    anchor = re.search(
        r"(?:^|\n)\s*第[一1]\s*编[\s\S]{0,800}?(?:^|\n)\s*第一条\s*(?:\n|$)",
        text,
        re.MULTILINE,
    )
    if anchor:
        return text[anchor.start() :].lstrip()
    anchor = re.search(
        r"(?:^|\n)\s*第一章[\s\S]{0,600}?(?:^|\n)\s*第一条\s*(?:\n|$)",
        text,
        re.MULTILINE,
    )
    if anchor:
        return text[anchor.start() :].lstrip()

    for m in _ARTICLE_LINE.finditer(text):
        tail = text[m.end() : m.end() + 400]
        plain = re.sub(r"[\s,，。；、…—\-]", "", tail)
        if len(plain) >= 30:
            return text[m.start() :].lstrip()
    return text


def prepare_legal_text(text: str) -> str:
    """清洗/分块/预览统一使用的正文整理（不依赖重启后端）。"""
    text = reflow_pdf_legal_text(text or "")
    return _trim_toc_before_body(text)


def _is_legal_document(text: str) -> bool:
    return len(_LEGAL_ARTICLE_DETECT.findall(prepare_legal_text(text))) >= 2


def _collect_article_starts(text: str) -> list[int]:
    starts: list[int] = []
    for m in _ARTICLE_LINE.finditer(text):
        starts.append(m.start())
    for m in _ARTICLE_LINE_INLINE.finditer(text):
        if m.start() not in starts:
            starts.append(m.start())
    starts.sort()
    deduped: list[int] = []
    for p in starts:
        if not deduped or p - deduped[-1] > 3:
            deduped.append(p)
    return deduped


def _split_legal_articles(text: str) -> list[str]:
    text = prepare_legal_text(text)
    starts = _collect_article_starts(text)
    if len(starts) < 2:
        parts = [s.strip() for s in re.split(rf"(?={_ARTICLE_NUM})", text) if s.strip()]
        parts = [p for p in parts if re.match(rf"^{_ARTICLE_NUM}", p)]
        if len(parts) >= 2:
            return parts
        return []

    segments: list[str] = []
    preamble = text[: starts[0]].strip()
    if preamble and len(preamble) > 20:
        segments.append(preamble)

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end].strip()
        if block:
            segments.append(block)
    return segments


def validate_legal_chunk_parts(parts: list[str], prepared_text: str) -> bool:
    """校验法条文档是否已按条切片（避免旧逻辑大块写入）。"""
    if not parts:
        return False
    expected = len(_LEGAL_ARTICLE_DETECT.findall(prepared_text))
    article_chunks = sum(
        1 for p in parts if re.match(rf"^{_ARTICLE_NUM}", (p or "").strip())
    )
    max_len = max(len(p) for p in parts)
    if expected >= 20:
        return article_chunks >= max(20, int(expected * 0.5)) and max_len < 800
    return article_chunks >= 2 and max_len < 1200


def _split_oversized(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    parts: list[str] = []
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            parts.append(para)
        else:
            for i in range(0, len(para), max_chars):
                parts.append(para[i : i + max_chars])
    return parts or [text[:max_chars]]


def _merge_segments(segments: list[str], max_chars: int) -> list[str]:
    parts: list[str] = []
    buf = ""
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        if len(buf) + len(seg) + 1 <= max_chars:
            buf = f"{buf}\n{seg}".strip() if buf else seg
        else:
            if buf:
                parts.append(buf)
            if len(seg) > max_chars:
                parts.extend(_split_oversized(seg, max_chars))
                buf = ""
            else:
                buf = seg
    if buf:
        parts.append(buf)
    return parts


def split_chunks(
    text: str,
    chunk_token_num: int = 512,
    delimiter: str = "",
    *,
    chunk_strategy: str = "auto",
) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    max_chars = max(chunk_token_num * 2, 200)
    use_legal = chunk_strategy == "legal_article" or (
        chunk_strategy != "naive" and _is_legal_document(text)
    )

    if delimiter and chunk_strategy != "legal_article":
        seps = [s.strip() for s in delimiter.split("\\n") if s.strip()]
        if not seps:
            seps = [delimiter]
        pattern = "|".join(re.escape(s) for s in seps)
        segments = [s.strip() for s in re.split(pattern, text) if s.strip()]
        parts = _merge_segments(segments, max_chars)
    elif use_legal:
        prepared = prepare_legal_text(text)
        segments = _split_legal_articles(prepared)
        if not segments:
            segments = _split_legal_articles(text)
        parts = []
        for seg in segments:
            parts.extend(_split_oversized(seg, max_chars))
        if not validate_legal_chunk_parts(parts, prepared):
            prepared2 = prepare_legal_text(collapse_vertical_legal_headers(text))
            segments2 = _split_legal_articles(prepared2)
            parts2 = []
            for seg in segments2:
                parts2.extend(_split_oversized(seg, max_chars))
            if validate_legal_chunk_parts(parts2, prepared2):
                parts = parts2
    else:
        segments = [s.strip() for s in re.split(r"\n{2,}", text) if s.strip()]
        parts = _merge_segments(segments, max_chars)

    if not parts:
        for i in range(0, len(text), max_chars):
            parts.append(text[i : i + max_chars])
    return parts


def reload_chunking_module():
    """每次清洗/分块前加载最新切片代码，无需重启 uvicorn。"""
    import app.services.chunking as mod

    return importlib.reload(mod)
