from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Chat, QaRecord
from app.services.qa_cache import qa_record_dict, sync_from_chat_messages
from app.utils import ok, err

router = APIRouter(
    prefix="/api/v1/admin/qa-records",
    tags=["qa-records"],
    dependencies=[Depends(require_admin)],
)


class QaRecordUpdate(BaseModel):
    confidence: str | None = Field(default=None, pattern="^(high|low)$")
    answer: str | None = None


@router.get("")
def list_qa_records(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    confidence: str | None = Query(None),
    keyword: str | None = Query(None),
):
    q = db.query(QaRecord).order_by(QaRecord.update_date.desc())
    if confidence in ("high", "low"):
        q = q.filter(QaRecord.confidence == confidence)
    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.filter(QaRecord.question.like(kw) | QaRecord.answer.like(kw))
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    chat_names: dict[str, str] = {}
    items = []
    for r in rows:
        chat_name = ""
        if r.chat_id:
            if r.chat_id not in chat_names:
                c = db.query(Chat).filter(Chat.id == r.chat_id).first()
                chat_names[r.chat_id] = c.name if c else ""
            chat_name = chat_names[r.chat_id]
        items.append(qa_record_dict(r, chat_name=chat_name))

    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/sync")
def sync_qa_records(db: Session = Depends(get_db)):
    added = sync_from_chat_messages(db)
    return ok({"added": added}, message=f"已同步 {added} 条问答记录")


@router.put("/{record_id}")
def update_qa_record(record_id: str, body: QaRecordUpdate, db: Session = Depends(get_db)):
    rec = db.query(QaRecord).filter(QaRecord.id == record_id).first()
    if not rec:
        return err("记录不存在", code=404)
    if body.confidence is not None:
        rec.confidence = body.confidence
    if body.answer is not None:
        rec.answer = body.answer.strip()
    db.commit()
    return ok(qa_record_dict(rec))


@router.delete("/{record_id}")
def delete_qa_record(record_id: str, db: Session = Depends(get_db)):
    rec = db.query(QaRecord).filter(QaRecord.id == record_id).first()
    if not rec:
        return err("记录不存在", code=404)
    db.delete(rec)
    db.commit()
    return ok()
