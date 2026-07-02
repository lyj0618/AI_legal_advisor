import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.deps import require_admin
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Chunk, Dataset, Document
from app.services.chunking import CHUNKING_VERSION, extract_text, prepare_legal_text
from app.services.text_cleaner import clean_document_text
from app.services.dataset_helpers import DEFAULT_CLEAN_OPTIONS, doc_dict, refresh_dataset_index
from app.services.doc_tasks import schedule_chunk, schedule_clean
from app.services.vector_index import vector_index_service
from app.utils import format_gmt, new_id, ok, err, paginate_query, paginated_data

router = APIRouter(prefix="/api/v1", tags=["datasets"], dependencies=[Depends(require_admin)])


class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    kb_type: str = "legal"
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


class DeleteIds(BaseModel):
    ids: list[str]


class ChunkUpdate(BaseModel):
    available: bool | None = None


class ChunkDelete(BaseModel):
    chunk_ids: list[str]


class BatchProcessBody(BaseModel):
    action: str = Field(pattern="^(clean|chunk)$")


def _dataset_dict(ds: Dataset, db: Session) -> dict:
    pc = ds.parser_config_dict
    return {
        "id": ds.id,
        "name": ds.name,
        "description": ds.description,
        "kb_type": getattr(ds, "kb_type", None) or "legal",
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


@router.get("/datasets")
def list_datasets(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
):
    q = db.query(Dataset).order_by(Dataset.create_date.desc())
    rows, total = paginate_query(q, page, page_size)
    return ok(paginated_data([_dataset_dict(d, db) for d in rows], total, page, page_size))


@router.post("/datasets")
def create_dataset(body: DatasetCreate, db: Session = Depends(get_db)):
    kb_type = body.kb_type if body.kb_type in ("legal", "case") else "legal"
    chunk_strategy = "legal_article" if kb_type == "legal" else "naive"
    ds = Dataset(
        id=new_id(),
        name=body.name,
        description=body.description,
        kb_type=kb_type,
        embedding_model=body.embedding_model,
        chunk_method=body.chunk_method,
        parser_config=json.dumps(
            {
                "chunk_token_num": 512,
                "delimiter": "",
                "chunk_strategy": chunk_strategy,
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
        vector_index_service.remove_dataset_index(did)
        db.delete(ds)
    db.commit()
    return ok()


@router.post("/datasets/{dataset_id}/rebuild-index")
def rebuild_dataset_index(dataset_id: str, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        return err("知识库不存在")
    count = refresh_dataset_index(db, dataset_id)
    return ok(
        {
            "dataset_id": dataset_id,
            "indexed_chunks": count,
            **vector_index_service.get_index_stats(dataset_id),
        },
        message=f"索引已重建，共 {count} 条向量",
    )


@router.get("/datasets/{dataset_id}/documents")
def list_documents(
    dataset_id: str,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
):
    q = db.query(Document).filter(Document.dataset_id == dataset_id).order_by(Document.create_date.desc())
    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.filter(Document.name.like(kw))
    rows, total = paginate_query(q, page, page_size)
    return ok(paginated_data([doc_dict(d) for d in rows], total, page, page_size))


@router.post("/datasets/{dataset_id}/documents")
async def upload_document(dataset_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        return err("知识库不存在")

    safe_name = Path(file.filename or "file.txt").name
    ext = Path(safe_name).suffix.lower()
    if ext not in settings.allowed_upload_ext_set:
        allowed = ", ".join(sorted(settings.allowed_upload_ext_set))
        return err(f"不支持的文件类型「{ext or '无扩展名'}」，仅允许：{allowed}")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        return err(f"文件过大（{len(content) / 1024 / 1024:.1f} MB），单文件上限 {settings.max_upload_mb} MB")
    if not content:
        return err("文件内容为空")

    upload_dir = settings.data_path / "uploads" / dataset_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{new_id()}_{safe_name}"
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
    return ok(doc_dict(doc))


@router.post("/datasets/{dataset_id}/documents/batch-process")
async def batch_process_documents(dataset_id: str, body: BatchProcessBody, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        return err("知识库不存在")
    docs = db.query(Document).filter(Document.dataset_id == dataset_id).all()
    to_schedule: list[str] = []
    skipped = 0
    for doc in docs:
        if body.action == "clean":
            if doc.clean_run == "RUNNING":
                skipped += 1
                continue
            doc.clean_run = "RUNNING"
            doc.clean_progress = 0.0
            to_schedule.append(doc.id)
        else:
            if (doc.clean_run or "0") != "1":
                skipped += 1
                continue
            if doc.run == "RUNNING":
                skipped += 1
                continue
            doc.run = "RUNNING"
            doc.process_begin_at = datetime.utcnow()
            doc.progress = 0.0
            to_schedule.append(doc.id)
    db.commit()
    for doc_id in to_schedule:
        if body.action == "clean":
            schedule_clean(dataset_id, doc_id)
        else:
            schedule_chunk(dataset_id, doc_id)
    label = "清洗" if body.action == "clean" else "分块"
    msg = f"已启动 {len(to_schedule)} 个{label}任务"
    if skipped:
        msg += f"，跳过 {skipped} 个"
    return ok({"scheduled": len(to_schedule), "skipped": skipped}, message=msg)


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
        doc.clean_run = "RUNNING"
        doc.clean_progress = 0.0
        db.commit()
        schedule_clean(dataset_id, doc_id)
        return ok(doc_dict(doc), message="清洗任务已启动")
    if body.run == "1":
        if (doc.clean_run or "0") != "1":
            return err("请先完成清洗后再分块")
        doc.run = "RUNNING"
        doc.process_begin_at = datetime.utcnow()
        doc.progress = 0.0
        db.commit()
        schedule_chunk(dataset_id, doc_id)
        return ok(doc_dict(doc), message="分块任务已启动")
    db.commit()
    if body.status is not None:
        refresh_dataset_index(db, dataset_id)
    return ok(doc_dict(doc))


@router.delete("/datasets/{dataset_id}/documents")
def delete_documents(dataset_id: str, body: DeleteIds, db: Session = Depends(get_db)):
    for doc_id in body.ids:
        doc = db.query(Document).filter(Document.id == doc_id, Document.dataset_id == dataset_id).first()
        if doc:
            if doc.location and Path(doc.location).exists():
                Path(doc.location).unlink(missing_ok=True)
            db.delete(doc)
    db.commit()
    refresh_dataset_index(db, dataset_id)
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
def list_chunks(
    dataset_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: str | None = Query(None),
):
    q = db.query(Chunk).filter(Chunk.document_id == doc_id).order_by(Chunk.id.asc())
    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.filter(Chunk.content.like(kw))
    rows, total = paginate_query(q, page, page_size)
    items = [
        {
            "id": c.id,
            "content": c.content,
            "available": c.available,
            "important_keywords": json.loads(c.important_keywords or "[]"),
        }
        for c in rows
    ]
    return ok(paginated_data(items, total, page, page_size))


@router.put("/datasets/{dataset_id}/documents/{doc_id}/chunks/{chunk_id}")
def update_chunk(dataset_id: str, doc_id: str, chunk_id: str, body: ChunkUpdate, db: Session = Depends(get_db)):
    ch = db.query(Chunk).filter(Chunk.id == chunk_id, Chunk.document_id == doc_id).first()
    if not ch:
        return err("切片不存在")
    if body.available is not None:
        ch.available = body.available
    db.commit()
    refresh_dataset_index(db, dataset_id)
    return ok()


@router.delete("/datasets/{dataset_id}/documents/{doc_id}/chunks")
def delete_chunks(dataset_id: str, doc_id: str, body: ChunkDelete, db: Session = Depends(get_db)):
    db.query(Chunk).filter(Chunk.id.in_(body.chunk_ids), Chunk.document_id == doc_id).delete(synchronize_session=False)
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        doc.chunk_count = db.query(Chunk).filter(Chunk.document_id == doc_id).count()
    db.commit()
    refresh_dataset_index(db, dataset_id)
    return ok()
