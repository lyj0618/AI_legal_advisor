import json
import uuid
from datetime import datetime


def new_id() -> str:
    return str(uuid.uuid4())


def ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data}


def err(message: str, code: int = 1):
    return {"code": code, "message": message, "data": None}


def format_gmt(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_json_field(raw: str, default=None):
    if default is None:
        default = {}
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return default


def strip_markdown(text: str) -> str:
    """去除回答中常见的 Markdown 格式符号，保留纯文本。"""
    if not text:
        return text
    import re

    s = text
    s = re.sub(r"```[^\n]*\n([\s\S]*?)```", r"\1", s)
    s = re.sub(r"```([^`]+)```", r"\1", s)
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"^>\s?", "", s, flags=re.MULTILINE)
    s = re.sub(r"^[-*+]\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*[-]{3,}\s*$", "", s, flags=re.MULTILINE)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def paginate_query(query, page: int, page_size: int):
    """SQLAlchemy 查询分页，返回 (rows, total)。"""
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


def paginated_data(items, total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size}
