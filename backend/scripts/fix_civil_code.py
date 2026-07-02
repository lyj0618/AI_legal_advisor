import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models import Document
from app.routers import datasets as datasets_router


async def main():
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.name.like("%.pdf")
        ).all()
        for doc in docs:
            if "民法典" not in (doc.name or "") and "bd53" not in (doc.location or ""):
                continue
            print("clean", doc.id, doc.name, "was", doc.chunk_count)
            from app.services.doc_tasks import run_clean_task
            await run_clean_task(doc.dataset_id, doc.id)
            d = db.query(Document).filter(Document.id == doc.id).first()
            from app.services.doc_tasks import run_chunk_task
            await run_chunk_task(d.dataset_id, d.id)
            r = {"code": 0}
            print(" ", r.get("message"), (r.get("data") or {}).get("chunk_count"))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
