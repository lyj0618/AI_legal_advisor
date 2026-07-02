from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Chat, ChatMessage, Chunk, Dataset, Document, User
from app.utils import format_gmt, ok

router = APIRouter(prefix="/api/v1/stats", tags=["stats"], dependencies=[Depends(require_admin)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    datasets = db.query(Dataset).count()
    documents = db.query(Document).count()
    chunks = db.query(Chunk).count()
    chats = db.query(Chat).filter(Chat.owner_username.isnot(None)).count()
    templates = db.query(Chat).filter(Chat.owner_username.is_(None), Chat.template_id.is_(None)).count()
    messages = db.query(ChatMessage).count()
    users = db.query(User).count()
    consultants = db.query(User).filter(User.role == "consultant").count()

    doc_status = (
        db.query(Document.run, func.count(Document.id))
        .group_by(Document.run)
        .all()
    )
    clean_status = (
        db.query(Document.clean_run, func.count(Document.id))
        .group_by(Document.clean_run)
        .all()
    )

    kb_types = (
        db.query(Dataset.kb_type, func.count(Dataset.id))
        .group_by(Dataset.kb_type)
        .all()
    )

    recent_msgs = (
        db.query(ChatMessage)
        .order_by(ChatMessage.create_date.desc())
        .limit(5)
        .all()
    )

    return ok(
        {
            "datasets": datasets,
            "documents": documents,
            "chunks": chunks,
            "chat_sessions": chats,
            "expert_templates": templates,
            "messages": messages,
            "users": users,
            "consultants": consultants,
            "doc_run_status": {k or "0": v for k, v in doc_status},
            "doc_clean_status": {k or "0": v for k, v in clean_status},
            "kb_types": {k or "legal": v for k, v in kb_types},
            "recent_messages": [
                {
                    "role": m.role,
                    "preview": (m.content or "")[:80],
                    "create_date": format_gmt(m.create_date),
                }
                for m in recent_msgs
            ],
        }
    )
