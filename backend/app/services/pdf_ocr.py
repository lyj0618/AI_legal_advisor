"""扫描版 PDF OCR（本地 Tesseract，可选依赖）。"""
from __future__ import annotations

from pathlib import Path


def ocr_pdf_to_text(file_path: Path, *, max_pages: int = 50) -> str:
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise ValueError(
            "扫描件 PDF 需安装可选依赖：pip install pymupdf pytesseract Pillow，"
            "并安装 Tesseract-OCR（含 chi_sim 语言包）"
        ) from e

    doc = fitz.open(str(file_path))
    parts: list[str] = []
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                parts.append(f"\n[OCR 已截断，仅处理前 {max_pages} 页]")
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            if text.strip():
                parts.append(text.strip())
    finally:
        doc.close()
    return "\n\n".join(parts)


def extract_pdf_text_with_ocr_fallback(file_path: Path, plain_text: str, *, min_chars: int = 80) -> tuple[str, str]:
    """文本过少时尝试 OCR。返回 (text, source_tag)。"""
    stripped = (plain_text or "").strip()
    if len(stripped) >= min_chars:
        return stripped, "pdf_text"
    try:
        ocr_text = ocr_pdf_to_text(file_path)
        if len(ocr_text.strip()) > len(stripped):
            return ocr_text.strip(), "pdf_ocr"
    except Exception:
        pass
    return stripped, "pdf_text"
