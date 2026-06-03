from fastapi import APIRouter, Depends

from app.deps import require_admin
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.rag import retrieve
from app.utils import ok, err

router = APIRouter(prefix="/api/v1", tags=["retrieval"], dependencies=[Depends(require_admin)])


class RetrievalRequest(BaseModel):
    dataset_ids: list[str]
    question: str
    top_k: int = 5


@router.post("/retrieval")
async def retrieval_test(body: RetrievalRequest, db: Session = Depends(get_db)):
    if not body.question.strip():
        return err("请输入测试问题")
    chunks = await retrieve(
        db,
        body.dataset_ids,
        body.question,
        top_k=body.top_k,
        similarity_threshold=0.0,
    )
    return ok({"chunks": chunks})
