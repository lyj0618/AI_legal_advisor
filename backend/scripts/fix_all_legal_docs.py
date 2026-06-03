"""清洗+分块修复所有法条类文档（民法典/劳动合同法）"""
import asyncio
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import Document
from app.routers import datasets as datasets_router

KEYWORDS = ("民法典", "劳动合同法")


async def main():
    db = SessionLocal()
    try:
        docs = db.query(Document).all()
        for doc in docs:
            if not any(k in (doc.name or "") for k in KEYWORDS):
                continue
            print("===", doc.name, doc.id, "chunks=", doc.chunk_count)
            await datasets_router._clean_document(db, doc)
            db2 = SessionLocal()
            doc = db2.query(Document).filter(Document.id == doc.id).first()
            db2.close()
            result = await datasets_router._chunk_document(db, doc)
            print(" ", result.get("message"), (result.get("data") or {}).get("chunk_count"))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
