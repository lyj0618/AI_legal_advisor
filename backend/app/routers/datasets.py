import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from app.deps import require_admin
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import Chunk, Dataset, Document
from app.services.chunking import (
    CHUNKING_VERSION,
    extract_text,
    prepare_legal_text,
    reload_chunking_module,
    split_chunks,
    validate_legal_chunk_parts,
)
from app.services.text_cleaner import clean_document_text
from app.services.dashscope import dashscope_client
from app.utils import format_gmt, new_id, ok, err

router = APIRouter(prefix="/api/v1", tags=["datasets"], dependencies=[Depends(require_admin)])


class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    embedding_model: str = "text-embedding-v2"
    chunk_method: str = "naive"


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    chunk_method: str | None = None
    permission: str | None = None
    pagerank: float | None = None
    parser_config: dict | None = None


class DocUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    clean: str | None = None
    run: str | None = None


DEFAULT_CLEAN_OPTIONS = {
    "enabled": True,
    "remove_noise": True,
    "remove_format": True,
    "process_tables": True,
    "remove_redundant": True,
    "normalize_chars": True,
}


class DeleteIds(BaseModel):
    ids: list[str]


class ChunkUpdate(BaseModel):
    available: bool | None = None


class ChunkDelete(BaseModel):
    chunk_ids: list[str]


def _dataset_dict(ds: Dataset, db: Session) -> dict:
    pc = ds.parser_config_dict
    return {
        "id": ds.id,
        "name": ds.name,
        "description": ds.description,
        "embedding_model": ds.embedding_model,
        "chunk_method": ds.chunk_method,
        "permission": ds.permission,
        "language": ds.language,
        "similarity_threshold": ds.similarity_threshold,
        "vector_similarity_weight": ds.vector_similarity_weight,
        "pagerank": ds.pagerank,
        "parser_config": pc,
        "document_count": ds.document_count(db),
        "create_date": format_gmt(ds.create_date),
        "pipeline_id": None,
    }


def _doc_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "name": doc.name,
        "location": doc.location,
        "status": doc.status,
        "chunk_method": doc.chunk_method,
        "chunk_count": doc.chunk_count,
        "clean_run": doc.clean_run or "0",
        "clean_progress": doc.clean_progress or 0.0,
        "run": doc.run,
        "progress": doc.progress,
        "create_date": format_gmt(doc.create_date),
        "process_begin_at": format_gmt(doc.process_begin_at) if doc.process_begin_at else None,
        "process_duration": doc.process_duration,
        "pipeline_id": None,
    }


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    items = db.query(Dataset).order_by(Dataset.create_date.desc()).all()
    return ok([_dataset_dict(d, db) for d in items])


@router.post("/datasets")
def create_dataset(body: DatasetCreate, db: Session = Depends(get_db)):
    ds = Dataset(
        id=new_id(),
        name=body.name,
        description=body.description,
        embedding_model=body.embedding_model,
        chunk_method=body.chunk_method,
        parser_config=json.dumps(
            {
                "chunk_token_num": 512,
                "delimiter": "",
                "chunk_strategy": "auto",
                "auto_keywords": 0,
                "auto_questions": 0,
                "filename_embd_weight": 0.1,
                "clean_options": dict(DEFAULT_CLEAN_OPTIONS),
            },
            ensure_ascii=False,
        ),
    )
    db.add(ds)
    db.commit()
    return ok(_dataset_dict(ds, db))


@router.put("/datasets/{dataset_id}")
def update_dataset(dataset_id: str, body: DatasetUpdate, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        return err("知识库不存在")
    if body.name is not None:
        ds.name = body.name
    if body.description is not None:
        ds.description = body.description
    if body.chunk_method is not None:
        ds.chunk_method = body.chunk_method
    if body.permission is not None:
        ds.permission = body.permission
    if body.pagerank is not None:
        ds.pagerank = body.pagerank
    if body.parser_config is not None:
        ds.parser_config = json.dumps(body.parser_config)
    db.commit()
    return ok(_dataset_dict(ds, db))


@router.delete("/datasets")
def delete_datasets(body: DeleteIds, db: Session = Depends(get_db)):
    for did in body.ids:
        ds = db.query(Dataset).filter(Dataset.id == did).first()
        if not ds:
            continue
        upload_dir = settings.data_path / "uploads" / did
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
        db.delete(ds)
    db.commit()
    return ok()


@router.get("/datasets/{dataset_id}/documents")
def list_documents(dataset_id: str, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.dataset_id == dataset_id).order_by(Document.create_date.desc()).all()
    return ok({"docs": [_doc_dict(d) for d in docs]})


@router.post("/datasets/{dataset_id}/documents")
async def upload_document(dataset_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        return err("知识库不存在")

    upload_dir = settings.data_path / "uploads" / dataset_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "file.txt").name
    file_path = upload_dir / f"{new_id()}_{safe_name}"

    content = await file.read()
    file_path.write_bytes(content)

    doc = Document(
        id=new_id(),
        dataset_id=dataset_id,
        name=safe_name,
        location=str(file_path),
        chunk_method=ds.chunk_method,
        progress=0.0,
        run="0",
        clean_run="0",
        clean_progress=0.0,
    )
    db.add(doc)
    db.commit()
    return ok(_doc_dict(doc))


@router.put("/datasets/{dataset_id}/documents/{doc_id}")
async def update_document(dataset_id: str, doc_id: str, body: DocUpdate, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.dataset_id == dataset_id).first()
    if not doc:
        return err("文档不存在")
    if body.name is not None:
        doc.name = body.name
    if body.status is not None:
        doc.status = body.status
    if body.clean == "1":
        return await _clean_document(db, doc)
    if body.run == "1":
        if (doc.clean_run or "0") != "1":
            return err("请先完成清洗后再分块")
        return await _chunk_document(db, doc)
    db.commit()
    return ok(_doc_dict(doc))


@router.delete("/datasets/{dataset_id}/documents")
def delete_documents(dataset_id: str, body: DeleteIds, db: Session = Depends(get_db)):
    for doc_id in body.ids:
        doc = db.query(Document).filter(Document.id == doc_id, Document.dataset_id == dataset_id).first()
        if doc:
            if doc.location and Path(doc.location).exists():
                Path(doc.location).unlink(missing_ok=True)
            db.delete(doc)
    db.commit()
    return ok()


@router.get("/datasets/{dataset_id}/documents/{doc_id}/cleaned-text")
def get_cleaned_text(dataset_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.dataset_id == dataset_id).first()
    if not doc:
        return err("文档不存在")
    if doc.cleaned_location and Path(doc.cleaned_location).exists():
        raw = Path(doc.cleaned_location).read_text(encoding="utf-8", errors="ignore")
        text = prepare_legal_text(raw)
        return ok({"text": text, "source": "cleaned", "chunking_version": CHUNKING_VERSION})
    if doc.location and Path(doc.location).exists():
        ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        pc = ds.parser_config_dict if ds else {}
        raw = extract_text(Path(doc.location), doc.name)
        text = clean_document_text(raw, pc.get("clean_options") or {})
        return ok({"text": text, "source": "preview"})
    return ok({"text": "", "source": "empty"})


@router.get("/datasets/{dataset_id}/documents/{doc_id}")
def download_document(dataset_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.dataset_id == dataset_id).first()
    if not doc or not doc.location or not Path(doc.location).exists():
        return err("文件不存在")
    return FileResponse(doc.location, filename=doc.name)


@router.get("/datasets/{dataset_id}/documents/{doc_id}/chunks")
def list_chunks(dataset_id: str, doc_id: str, db: Session = Depends(get_db)):
    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == doc_id)
        .order_by(Chunk.id.asc())
        .all()
    )
    return ok(
        {
            "chunks": [
                {
                    "id": c.id,
                    "content": c.content,
                    "available": c.available,
                    "important_keywords": json.loads(c.important_keywords or "[]"),
                }
                for c in chunks
            ]
        }
    )


@router.put("/datasets/{dataset_id}/documents/{doc_id}/chunks/{chunk_id}")
def update_chunk(dataset_id: str, doc_id: str, chunk_id: str, body: ChunkUpdate, db: Session = Depends(get_db)):
    ch = db.query(Chunk).filter(Chunk.id == chunk_id, Chunk.document_id == doc_id).first()
    if not ch:
        return err("切片不存在")
    if body.available is not None:
        ch.available = body.available
    db.commit()
    return ok()


@router.delete("/datasets/{dataset_id}/documents/{doc_id}/chunks")
def delete_chunks(dataset_id: str, doc_id: str, body: ChunkDelete, db: Session = Depends(get_db)):
    db.query(Chunk).filter(Chunk.id.in_(body.chunk_ids), Chunk.document_id == doc_id).delete(synchronize_session=False)
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        doc.chunk_count = db.query(Chunk).filter(Chunk.document_id == doc_id).count()
    db.commit()
    return ok()


async def _clean_document(db: Session, doc: Document):
    ds = db.query(Dataset).filter(Dataset.id == doc.dataset_id).first()
    if not ds:
        return err("知识库不存在")

    doc_id = doc.id
    doc.clean_run = "RUNNING"
    doc.clean_progress = 0.0
    db.commit()

    parser_config = ds.parser_config_dict
    file_path = Path(doc.location)
    file_name = doc.name

    try:
        raw_text = extract_text(file_path, file_name)
        clean_opts = {**DEFAULT_CLEAN_OPTIONS, **(parser_config.get("clean_options") or {})}
        ch = reload_chunking_module()
        cleaned = clean_document_text(raw_text, clean_opts)
        cleaned = ch.prepare_legal_text(cleaned)
        cleaned_path = file_path.parent / f"{doc_id}_cleaned.txt"
        cleaned_path.write_text(cleaned, encoding="utf-8")

        write_db = SessionLocal()
        try:
            wdoc = write_db.query(Document).filter(Document.id == doc_id).first()
            if not wdoc:
                return err("文档不存在")
            wdoc.cleaned_location = str(cleaned_path)
            wdoc.clean_run = "1"
            wdoc.clean_progress = 1.0
            write_db.commit()
            return ok(_doc_dict(wdoc))
        finally:
            write_db.close()
    except Exception as e:
        fail_db = SessionLocal()
        try:
            fdoc = fail_db.query(Document).filter(Document.id == doc_id).first()
            if fdoc:
                fdoc.clean_run = "0"
                fdoc.clean_progress = 0.0
                fail_db.commit()
        finally:
            fail_db.close()
        return err(f"清洗失败: {e}")


async def _chunk_document(db: Session, doc: Document):
    ds = db.query(Dataset).filter(Dataset.id == doc.dataset_id).first()
    if not ds:
        return err("知识库不存在")

    doc_id = doc.id
    cleaned_path = Path(doc.cleaned_location) if doc.cleaned_location else None
    if not cleaned_path or not cleaned_path.exists():
        return err("请先完成清洗")

    doc.run = "RUNNING"
    doc.process_begin_at = datetime.utcnow()
    doc.progress = 0.0
    db.commit()

    parser_config = ds.parser_config_dict
    begin_at = doc.process_begin_at

    try:
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
            return err("分块结果为空，请检查清洗正文")
        if strategy == "legal_article" and not ch.validate_legal_chunk_parts(parts, prepared):
            return err(
                "法条切片校验未通过（仍为大块合并）。请点击「清洗」后重新「分块」，"
                f"或联系管理员（切片版本 {CHUNKING_VERSION}）"
            )

        write_db = SessionLocal()
        chunk_rows: list[tuple[str, str]] = []
        try:
            wdoc = write_db.query(Document).filter(Document.id == doc_id).first()
            if not wdoc:
                return err("文档不存在")
            write_db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
            for part in parts:
                cid = new_id()
                chunk_rows.append((cid, part))
                write_db.add(
                    Chunk(
                        id=cid,
                        document_id=doc_id,
                        content=part,
                        available=True,
                        embedding="[]",
                    )
                )
            wdoc.chunk_count = len(parts)
            wdoc.progress = 0.5
            wdoc.run = "RUNNING"
            write_db.commit()
        finally:
            write_db.close()

        embed_note = ""
        try:
            embeddings = await dashscope_client.embed_texts(parts) if parts else []
            emb_db = SessionLocal()
            try:
                for i, (cid, _) in enumerate(chunk_rows):
                    emb = embeddings[i] if i < len(embeddings) else []
                    ch = emb_db.query(Chunk).filter(Chunk.id == cid).first()
                    if ch:
                        ch.embedding = json.dumps(emb)
                wdoc = emb_db.query(Document).filter(Document.id == doc_id).first()
                if wdoc:
                    wdoc.progress = 1.0
                    wdoc.run = "1"
                    wdoc.process_duration = (datetime.utcnow() - begin_at).total_seconds() if begin_at else 0
                emb_db.commit()
            finally:
                emb_db.close()
        except Exception as embed_err:
            embed_note = f"（向量嵌入失败：{embed_err}，切片已保存，检索可能不可用）"
            done_db = SessionLocal()
            try:
                wdoc = done_db.query(Document).filter(Document.id == doc_id).first()
                if wdoc:
                    wdoc.progress = 1.0
                    wdoc.run = "1"
                    wdoc.process_duration = (datetime.utcnow() - begin_at).total_seconds() if begin_at else 0
                    done_db.commit()
                    return ok(_doc_dict(wdoc), message=f"已完成解析，共 {len(parts)} 条{embed_note}")
            finally:
                done_db.close()

        final_db = SessionLocal()
        try:
            wdoc = final_db.query(Document).filter(Document.id == doc_id).first()
            return ok(_doc_dict(wdoc), message=f"已完成解析，共 {len(parts)} 条")
        finally:
            final_db.close()
    except Exception as e:
        fail_db = SessionLocal()
        try:
            fdoc = fail_db.query(Document).filter(Document.id == doc_id).first()
            if fdoc:
                fdoc.run = "0"
                fdoc.progress = 0.0
                fail_db.commit()
        finally:
            fail_db.close()
        return err(f"分块失败: {e}")
