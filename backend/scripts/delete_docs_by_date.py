"""按上传日期批量删除知识库文档。用法: python scripts/delete_docs_by_date.py 2026-06-23"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import Document
from app.services.dataset_helpers import refresh_dataset_index


def main(target: str) -> None:
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(func.date(Document.create_date) == target).all()
        print(f"Found {len(docs)} documents on {target}")
        dataset_ids: set[str] = set()
        for doc in docs:
            dataset_ids.add(doc.dataset_id)
            for path_attr in ("location", "cleaned_location"):
                p = getattr(doc, path_attr, "") or ""
                if p:
                    Path(p).unlink(missing_ok=True)
            print(f"  delete: {doc.id} | {doc.name}")
            db.delete(doc)
        db.commit()
        for ds_id in dataset_ids:
            n = refresh_dataset_index(db, ds_id)
            print(f"Rebuilt index for dataset {ds_id}: {n} chunks")
        remaining = db.query(Document).filter(func.date(Document.create_date) == target).count()
        print(f"Done. Deleted {len(docs)}, remaining on {target}: {remaining}")
    finally:
        db.close()


if __name__ == "__main__":
    day = sys.argv[1] if len(sys.argv) > 1 else "2026-06-23"
    main(day)
