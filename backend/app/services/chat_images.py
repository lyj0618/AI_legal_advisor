"""对话图片上传与多模态消息构建。"""
from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

from fastapi import UploadFile

from app.config import settings
from app.utils import new_id, strip_markdown

ALLOWED_CHAT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def chat_images_dir(chat_id: str) -> Path:
    d = settings.data_path / "chat_images" / chat_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_ext(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in ALLOWED_CHAT_IMAGE_EXTENSIONS:
        return ext
    return ".jpg"


def validate_chat_image(file: UploadFile, data: bytes) -> None:
    if not data:
        raise ValueError("图片文件为空")
    max_bytes = settings.max_chat_image_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"单张图片不能超过 {settings.max_chat_image_mb}MB")
    ext = _safe_ext(file.filename or "")
    if ext not in ALLOWED_CHAT_IMAGE_EXTENSIONS:
        raise ValueError("仅支持 JPG、PNG、WEBP、GIF、BMP 格式图片")


def save_chat_image(chat_id: str, file: UploadFile, data: bytes) -> dict:
    validate_chat_image(file, data)
    image_id = new_id()
    ext = _safe_ext(file.filename or "")
    path = chat_images_dir(chat_id) / f"{image_id}{ext}"
    path.write_bytes(data)
    name = (file.filename or f"image{ext}").strip() or f"image{ext}"
    return {
        "id": image_id,
        "name": name,
        "path": str(path),
        "mime": mimetypes.guess_type(name)[0] or "image/jpeg",
    }


def get_chat_image_path(chat_id: str, image_id: str) -> Path | None:
    folder = chat_images_dir(chat_id)
    for ext in ALLOWED_CHAT_IMAGE_EXTENSIONS:
        p = folder / f"{image_id}{ext}"
        if p.is_file():
            return p
    return None


def image_to_data_url(path: Path) -> str:
    data = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def resolve_image_data_urls(chat_id: str, image_ids: list[str]) -> list[str]:
    urls: list[str] = []
    for image_id in image_ids:
        image_id = (image_id or "").strip()
        if not image_id or not re.fullmatch(r"[a-f0-9-]{36}", image_id):
            continue
        path = get_chat_image_path(chat_id, image_id)
        if path:
            urls.append(image_to_data_url(path))
    return urls


def build_user_message_content(question: str, image_data_urls: list[str]) -> str | list[dict]:
    text = (question or "").strip()
    if not image_data_urls:
        return text
    if not text:
        text = "请仔细解读图片中的文字与关键信息，结合知识库与专业常识给出分析回答。"
    parts: list[dict] = [{"type": "text", "text": text}]
    for url in image_data_urls:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


IMAGE_ANALYZE_PROMPT = """请客观、完整地提取这张图片中的文字与关键信息。

要求：
1. 直接输出识别到的正文，禁止使用任何 Markdown 符号（不要用 #、**、*、`、> 等）
2. 不要加「图片中的文字内容」等小标题，不要写前言或总结
3. 段落之间不要空行，每段紧接上一段，仅用单个换行分隔
4. 若有多条，可用「1. 2. 3.」纯文本编号
5. 只输出识别结果，不要给建议或结论"""


def _clean_image_analysis(text: str) -> str:
    s = strip_markdown((text or "").strip())
    if not s:
        return ""
    drop_titles = {
        "图片中的文字内容",
        "文字内容",
        "关键要素",
        "文档类型或主题",
        "表格、图表、印章、签名、日期等关键要素",
    }
    lines: list[str] = []
    for line in s.splitlines():
        t = line.strip()
        if not t:
            continue
        if t in drop_titles:
            continue
        if re.match(r"^图片中的\S{0,20}$", t):
            continue
        lines.append(t)
    return "\n".join(lines)


async def analyze_chat_image_content(path: Path) -> str:
    from app.services.dashscope import dashscope_client

    data_url = image_to_data_url(path)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": IMAGE_ANALYZE_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    raw = (await dashscope_client.chat_completion(messages, temperature=0.1)).strip()
    return _clean_image_analysis(raw)
