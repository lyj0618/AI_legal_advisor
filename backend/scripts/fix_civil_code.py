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
            await datasets_router._clean_document(db, doc)
            d = db.query(Document).filter(Document.id == doc.id).first()
            r = await datasets_router._chunk_document(db, d)
            print(" ", r.get("message"), (r.get("data") or {}).get("chunk_count"))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
