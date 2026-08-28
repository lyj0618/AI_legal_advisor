"""文档（知识库）内嵌图片 serve 接口。

图片在清洗阶段由 chunking 提取到 data_path/doc_images/{doc_id}/，
检索/回答时通过 chunk.images 中的文件名引用，前端按此接口拉取原图。
"""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.deps import CurrentUser, require_auth

router = APIRouter(prefix="/api/v1", tags=["documents"])

_SAFE = re.compile(r"^[\w.\-]+$")
_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


@router.get("/documents/{doc_id}/images/{image_id}")
def get_document_image(
    doc_id: str,
    image_id: str,
    _user: CurrentUser = Depends(require_auth),
):
    if not _SAFE.match(doc_id) or not _SAFE.match(image_id):
        raise HTTPException(status_code=400, detail="非法的图片标识")
    folder = (settings.data_path / "doc_images" / doc_id).resolve()
    path = (folder / image_id).resolve()
    # 防目录穿越：解析后的路径必须仍是 folder 的直接子文件
    if path.parent != folder:
        raise HTTPException(status_code=400, detail="非法的图片路径")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    ext = path.suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=404, detail="不支持的图片类型")
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "image/png")
