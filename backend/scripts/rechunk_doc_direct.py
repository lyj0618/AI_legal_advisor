"""直接重新分块（用法: python scripts/rechunk_doc_direct.py [document_id]）"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import Document
from app.routers import datasets as datasets_router

DEFAULT_DOC = "702343fe-0432-4000-9bc1-724bad00e060"


async def main():
    doc_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DOC
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            print("文档不存在:", doc_id)
            return 1
        print("rechunk:", doc.name, doc_id)
        result = await datasets_router._chunk_document(db, doc)
        print(result)
        db2 = SessionLocal()
        n = db2.query(Document).filter(Document.id == doc_id).first().chunk_count
        db2.close()
        return 0 if n and n > 50 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
