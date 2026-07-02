import json

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document
from app.services.vector_index import vector_index_service
from app.utils import format_gmt

DEFAULT_CLEAN_OPTIONS = {
    "enabled": True,
    "remove_noise": True,
    "remove_format": True,
    "process_tables": True,
    "remove_redundant": True,
    "normalize_chars": True,
}


def doc_dict(doc: Document) -> dict:
    timeliness = None
    if getattr(doc, "timeliness_json", None):
        try:
            timeliness = json.loads(doc.timeliness_json)
        except json.JSONDecodeError:
            timeliness = None
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
        "timeliness": timeliness,
        "create_date": format_gmt(doc.create_date),
        "process_begin_at": format_gmt(doc.process_begin_at) if doc.process_begin_at else None,
        "process_duration": doc.process_duration,
        "pipeline_id": None,
    }


def refresh_dataset_index(db: Session, dataset_id: str) -> int:
    if not settings.use_vector_index:
        return 0
    return vector_index_service.rebuild_dataset_index(db, dataset_id)
