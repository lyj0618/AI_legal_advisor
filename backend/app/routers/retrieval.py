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


class BatchRetrievalRequest(BaseModel):
    dataset_ids: list[str]
    questions: list[str]
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


@router.post("/retrieval/batch")
async def batch_retrieval_test(body: BatchRetrievalRequest, db: Session = Depends(get_db)):
    questions = [q.strip() for q in body.questions if q and q.strip()]
    if not questions:
        return err("请至少输入一个测试问题")
    results = []
    for q in questions:
        chunks = await retrieve(
            db,
            body.dataset_ids,
            q,
            top_k=body.top_k,
            similarity_threshold=0.0,
        )
        top_sim = chunks[0]["similarity"] if chunks else 0.0
        results.append(
            {
                "question": q,
                "hit_count": len(chunks),
                "top_similarity": top_sim,
                "chunks": chunks,
            }
        )
    return ok({"results": results, "total": len(results)})
