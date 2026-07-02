"""为所有知识库重建 FAISS 向量索引。

用法:
  cd backend
  python scripts/rebuild_indexes.py
  python scripts/rebuild_indexes.py <dataset_id>
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.models import Dataset
from app.services.vector_index import vector_index_service


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        if len(sys.argv) > 1:
            ids = [sys.argv[1]]
        else:
            ids = [d.id for d in db.query(Dataset).all()]
        if not ids:
            print("无知识库")
            return 0
        for ds_id in ids:
            count = vector_index_service.rebuild_dataset_index(db, ds_id)
            print(f"{ds_id}: {count} vectors")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
