"""向量索引与暴力检索结果一致性测试（无需 DashScope）。"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import Base, SessionLocal, engine
from app.models import Chunk, Dataset, Document
from app.services.vector_index import VectorIndexService
from app.utils import new_id

TEST_DATA = Path(__file__).resolve().parents[1] / "data" / "test_indexes"


def _setup_db():
    TEST_DATA.mkdir(parents=True, exist_ok=True)
    engine.dispose()
    test_engine = __import__("sqlalchemy", fromlist=["create_engine"]).create_engine(
        f"sqlite:///{TEST_DATA / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    return SessionLocal(bind=test_engine)


def test_index_search_matches_brute_force():
    db = _setup_db()
    svc = VectorIndexService(TEST_DATA)
    ds_id = new_id()
    doc_id = new_id()

    db.add(Dataset(id=ds_id, name="测试库"))
    db.add(Document(id=doc_id, dataset_id=ds_id, name="a.txt", status="1"))
    rng = np.random.default_rng(42)
    dim = 16
    query = rng.random(dim).astype(np.float32).tolist()

    for i in range(30):
        emb = rng.random(dim).astype(np.float32).tolist()
        db.add(
            Chunk(
                id=new_id(),
                document_id=doc_id,
                content=f"chunk-{i}",
                available=True,
                embedding=json.dumps(emb),
            )
        )
    db.commit()

    svc.rebuild_dataset_index(db, ds_id)
    hits = svc.search(db, [ds_id], query, top_k=5, similarity_threshold=0.0)

    # brute force
    chunks = db.query(Chunk).filter(Chunk.document_id == doc_id, Chunk.available.is_(True)).all()
    scored = []
    q = np.array(query, dtype=np.float32)
    qn = q / max(np.linalg.norm(q), 1e-12)
    for ch in chunks:
        emb = np.array(json.loads(ch.embedding), dtype=np.float32)
        en = emb / max(np.linalg.norm(emb), 1e-12)
        scored.append((float(np.dot(qn, en)), ch.id))
    scored.sort(reverse=True)
    brute_top = [cid for _, cid in scored[:5]]

    index_top = [h[1] for h in hits]
    assert index_top == brute_top
    print("test_index_search_matches_brute_force: OK")


if __name__ == "__main__":
    test_index_search_matches_brute_force()
