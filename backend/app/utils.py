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
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def parse_json_field(raw: str, default=None):
    if default is None:
        default = {}
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return default
