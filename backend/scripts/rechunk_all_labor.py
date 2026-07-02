"""重新分块所有劳动合同法文档（旧版大块切片）"""
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
        docs = (
            db.query(Document)
            .filter(Document.name.like("%劳动合同法%"))
            .all()
        )
        for doc in docs:
            n = doc.chunk_count or 0
            if n > 0 and n < 50:
                print("rechunk", doc.name, doc.id, "was", n)
                from app.services.doc_tasks import run_chunk_task
                await run_chunk_task(doc.dataset_id, doc.id)
                db2 = SessionLocal()
                fresh = db2.query(Document).filter(Document.id == doc.id).first()
                print("  ->", fresh.chunk_count if fresh else "?")
                db2.close()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
