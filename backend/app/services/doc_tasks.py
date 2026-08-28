"""文档清洗/分块后台任务 + WebSocket 进度推送。"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import Chunk, Dataset, Document
from app.services.dataset_helpers import DEFAULT_CLEAN_OPTIONS, doc_dict, refresh_dataset_index
from app.services.chunking import (
    CHUNKING_VERSION,
    extract_text,
    extract_text_with_images,
    reload_chunking_module,
    split_chunks,
    validate_legal_chunk_parts,
)
from app.services.dashscope import dashscope_client
from app.services.legal_timeliness import analyze_legal_timeliness
from app.services.progress_hub import progress_hub
from app.services.text_cleaner import clean_document_text
from app.utils import new_id


async def _broadcast(dataset_id: str, doc_id: str, doc_data: dict, *, message: str = "", event: str = "doc_update"):
    await progress_hub.broadcast(
        f"dataset:{dataset_id}",
        {"type": event, "doc_id": doc_id, "doc": doc_data, "message": message},
    )


def _associate_images(parts: list[str], image_marks: list[str]) -> list[tuple[str, list[str]]]:
    """将文档图片按顺序关联到分块：第 i 张图归第 i 个分块，多余的图归入最后一个分块。"""
    if not image_marks:
        return [(p, []) for p in parts]
    n = len(parts)
    result: list[tuple[str, list[str]]] = [(p, []) for p in parts]
    for i, fn in enumerate(image_marks):
        idx = min(i, n - 1) if n else 0
        result[idx][1].append(fn)
    return result


def _load_image_sidecar(cleaned_path: Path, doc_id: str) -> tuple[list[str], list[list[str]]]:
    """读取清洗阶段落盘的图片名 sidecar 文件，返回 (全部图片, 按章节归类的图片)。"""
    sidecar = cleaned_path.parent / f"{doc_id}_images.json"
    if not sidecar.exists():
        return [], []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if isinstance(data, list):
            # 兼容旧格式
            return data, []
        if isinstance(data, dict):
            marks = data.get("image_marks", [])
            sections = data.get("image_sections", [])
            return marks, sections
    except Exception:
        pass
    return [], []


async def run_clean_task(dataset_id: str, doc_id: str) -> None:
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id, Document.dataset_id == dataset_id).first()
        if not doc:
            return
        ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not ds:
            return

        parser_config = ds.parser_config_dict
        file_path = Path(doc.location)
        file_name = doc.name

        def _cpu_clean():
            raw_text, image_marks, image_sections = extract_text_with_images(file_path, file_name, doc_id)
            clean_opts = {**DEFAULT_CLEAN_OPTIONS, **(parser_config.get("clean_options") or {})}
            ch = reload_chunking_module()
            cleaned = clean_document_text(raw_text, clean_opts)
            cleaned = ch.prepare_legal_text(cleaned)
            timeliness = analyze_legal_timeliness(cleaned)
            cleaned_path = file_path.parent / f"{doc_id}_cleaned.txt"
            cleaned_path.write_text(cleaned, encoding="utf-8")
            # 落盘图片名 sidecar（含章节分组），供分块步骤把截图归到对应问题条目
            image_sidecar = cleaned_path.parent / f"{doc_id}_images.json"
            sidecar_payload = {
                "image_marks": image_marks,
                "image_sections": image_sections,
            }
            image_sidecar.write_text(json.dumps(sidecar_payload, ensure_ascii=False), encoding="utf-8")
            return cleaned_path, timeliness

        cleaned_path, timeliness = await asyncio.to_thread(_cpu_clean)

        wdb = SessionLocal()
        try:
            wdoc = wdb.query(Document).filter(Document.id == doc_id).first()
            if not wdoc:
                return
            wdoc.cleaned_location = str(cleaned_path)
            wdoc.clean_run = "1"
            wdoc.clean_progress = 1.0
            wdoc.timeliness_json = json.dumps(timeliness, ensure_ascii=False)
            wdb.commit()
            await _broadcast(dataset_id, doc_id, doc_dict(wdoc), message="清洗完成")
        finally:
            wdb.close()
    except Exception as e:
        fdb = SessionLocal()
        try:
            fdoc = fdb.query(Document).filter(Document.id == doc_id).first()
            if fdoc:
                fdoc.clean_run = "0"
                fdoc.clean_progress = 0.0
                fdb.commit()
                await _broadcast(dataset_id, doc_id, doc_dict(fdoc), message=f"清洗失败: {e}", event="doc_error")
        finally:
            fdb.close()
    finally:
        db.close()


async def run_chunk_task(dataset_id: str, doc_id: str) -> None:
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id, Document.dataset_id == dataset_id).first()
        if not doc:
            return
        ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not ds:
            return
        cleaned_path = Path(doc.cleaned_location) if doc.cleaned_location else None
        if not cleaned_path or not cleaned_path.exists():
            await _broadcast(dataset_id, doc_id, doc_dict(doc), message="请先完成清洗", event="doc_error")
            return

        begin_at = datetime.utcnow()
        parser_config = ds.parser_config_dict

        def _cpu_split():
            ch = reload_chunking_module()
            cleaned = cleaned_path.read_text(encoding="utf-8", errors="ignore")
            prepared = ch.prepare_legal_text(cleaned)
            strategy = parser_config.get("chunk_strategy") or "auto"
            if strategy == "auto" and ch._is_legal_document(cleaned):
                strategy = "legal_article"
            parts = ch.split_chunks(
                cleaned,
                chunk_token_num=int(parser_config.get("chunk_token_num", 512)),
                delimiter=parser_config.get("delimiter") or "",
                chunk_strategy=strategy,
            )
            if not parts:
                raise ValueError("分块结果为空")
            if strategy == "legal_article" and not ch.validate_legal_chunk_parts(parts, prepared):
                # 该文档并非标准法条结构，法条切片校验不过；优先按编号章节切片，否则回退通用分块
                fallback_strategy = "numbered_section" if ch._has_numbered_sections(cleaned) else "naive"
                strategy = fallback_strategy
                parts = ch.split_chunks(
                    cleaned,
                    chunk_token_num=int(parser_config.get("chunk_token_num", 512)),
                    delimiter=parser_config.get("delimiter") or "",
                    chunk_strategy=fallback_strategy,
                )
                if not parts:
                    raise ValueError("分块结果为空（通用分块仍失败）")
            image_marks, image_sections = _load_image_sidecar(cleaned_path, doc_id)
            # 如果章节分组与分块数量一致，直接把每章节的图片归到对应分块
            if image_sections and len(image_sections) == len(parts):
                return [(part, imgs) for part, imgs in zip(parts, image_sections)]
            return _associate_images(parts, image_marks)

        parts_with_images = await asyncio.to_thread(_cpu_split)

        write_db = SessionLocal()
        chunk_rows: list[tuple[str, str]] = []
        try:
            wdoc = write_db.query(Document).filter(Document.id == doc_id).first()
            if not wdoc:
                return
            write_db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
            for part, imgs in parts_with_images:
                cid = new_id()
                chunk_rows.append((cid, part))
                write_db.add(
                    Chunk(
                        id=cid,
                        document_id=doc_id,
                        content=part,
                        images=json.dumps(imgs, ensure_ascii=False),
                        available=True,
                        embedding="[]",
                    )
                )
            wdoc.chunk_count = len(parts_with_images)
            wdoc.progress = 0.5
            wdoc.run = "RUNNING"
            write_db.commit()
            await _broadcast(dataset_id, doc_id, doc_dict(wdoc), message=f"切片完成 {len(parts_with_images)} 条，正在嵌入…")
        finally:
            write_db.close()

        embed_note = ""
        try:
            texts_to_embed = [part for part, _ in parts_with_images]
            embeddings = await dashscope_client.embed_texts(texts_to_embed) if texts_to_embed else []
            emb_db = SessionLocal()
            try:
                for i, (cid, _) in enumerate(chunk_rows):
                    emb = embeddings[i] if i < len(embeddings) else []
                    ch_row = emb_db.query(Chunk).filter(Chunk.id == cid).first()
                    if ch_row:
                        ch_row.embedding = json.dumps(emb)
                wdoc = emb_db.query(Document).filter(Document.id == doc_id).first()
                if wdoc:
                    wdoc.progress = 1.0
                    wdoc.run = "1"
                    wdoc.process_duration = (datetime.utcnow() - begin_at).total_seconds()
                emb_db.commit()
            finally:
                emb_db.close()
        except Exception as embed_err:
            embed_note = f"（嵌入失败：{embed_err}）"
            done_db = SessionLocal()
            try:
                wdoc = done_db.query(Document).filter(Document.id == doc_id).first()
                if wdoc:
                    wdoc.progress = 1.0
                    wdoc.run = "1"
                    wdoc.process_duration = (datetime.utcnow() - begin_at).total_seconds()
                    done_db.commit()
            finally:
                done_db.close()

        final_db = SessionLocal()
        try:
            wdoc = final_db.query(Document).filter(Document.id == doc_id).first()
            if wdoc:
                refresh_dataset_index(final_db, dataset_id)
                msg = f"分块完成，共 {len(parts_with_images)} 条{embed_note}"
                await _broadcast(dataset_id, doc_id, doc_dict(wdoc), message=msg)
        finally:
            final_db.close()
    except Exception as e:
        fdb = SessionLocal()
        try:
            fdoc = fdb.query(Document).filter(Document.id == doc_id).first()
            if fdoc:
                fdoc.run = "0"
                fdoc.progress = 0.0
                fdb.commit()
                await _broadcast(dataset_id, doc_id, doc_dict(fdoc), message=f"分块失败: {e}", event="doc_error")
        finally:
            fdb.close()
    finally:
        db.close()


def schedule_clean(dataset_id: str, doc_id: str) -> None:
    asyncio.create_task(run_clean_task(dataset_id, doc_id))


def schedule_chunk(dataset_id: str, doc_id: str) -> None:
    asyncio.create_task(run_chunk_task(dataset_id, doc_id))
