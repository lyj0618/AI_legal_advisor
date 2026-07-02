"""按知识库维护 FAISS 向量索引（IndexFlatIP + L2 归一化 ≈ 余弦相似度）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document


class VectorIndexService:
    def __init__(self, data_path: Path):
        self.index_dir = data_path / "indexes"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._index_cache: dict[str, faiss.Index] = {}
        self._meta_cache: dict[str, dict[str, Any]] = {}

    def _index_path(self, dataset_id: str) -> Path:
        return self.index_dir / f"{dataset_id}.faiss"

    def _meta_path(self, dataset_id: str) -> Path:
        return self.index_dir / f"{dataset_id}.meta.json"

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        return vectors / norms

    def _invalidate_cache(self, dataset_id: str) -> None:
        self._index_cache.pop(dataset_id, None)
        self._meta_cache.pop(dataset_id, None)

    def remove_dataset_index(self, dataset_id: str) -> None:
        self._invalidate_cache(dataset_id)
        self._index_path(dataset_id).unlink(missing_ok=True)
        self._meta_path(dataset_id).unlink(missing_ok=True)

    def get_index_stats(self, dataset_id: str) -> dict[str, Any]:
        meta_path = self._meta_path(dataset_id)
        if not meta_path.exists():
            return {"dataset_id": dataset_id, "indexed": False, "count": 0}
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"dataset_id": dataset_id, "indexed": False, "count": 0}
        return {
            "dataset_id": dataset_id,
            "indexed": True,
            "count": int(meta.get("count") or 0),
            "dim": meta.get("dim"),
        }

    def rebuild_dataset_index(self, db: Session, dataset_id: str) -> int:
        """从数据库重建指定知识库的 FAISS 索引，返回入库向量数。"""
        docs = (
            db.query(Document)
            .filter(Document.dataset_id == dataset_id, Document.status == "1")
            .all()
        )
        doc_ids = [d.id for d in docs]
        if not doc_ids:
            self.remove_dataset_index(dataset_id)
            return 0

        rows = (
            db.query(Chunk)
            .filter(Chunk.document_id.in_(doc_ids), Chunk.available.is_(True))
            .all()
        )

        vectors: list[list[float]] = []
        chunk_ids: list[str] = []
        document_ids: list[str] = []
        for ch in rows:
            if not ch.embedding:
                continue
            try:
                emb = json.loads(ch.embedding)
            except json.JSONDecodeError:
                continue
            if not emb:
                continue
            vectors.append(emb)
            chunk_ids.append(ch.id)
            document_ids.append(ch.document_id)

        if not vectors:
            self.remove_dataset_index(dataset_id)
            return 0

        mat = np.array(vectors, dtype=np.float32)
        mat = self._normalize(mat)
        dim = int(mat.shape[1])
        index = faiss.IndexFlatIP(dim)
        index.add(mat)

        faiss.write_index(index, str(self._index_path(dataset_id)))
        meta = {
            "dataset_id": dataset_id,
            "chunk_ids": chunk_ids,
            "document_ids": document_ids,
            "dim": dim,
            "count": len(chunk_ids),
        }
        self._meta_path(dataset_id).write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )
        self._index_cache[dataset_id] = index
        self._meta_cache[dataset_id] = meta
        return len(chunk_ids)

    def _load(self, db: Session, dataset_id: str) -> tuple[faiss.Index | None, dict[str, Any] | None]:
        if dataset_id in self._index_cache and dataset_id in self._meta_cache:
            return self._index_cache[dataset_id], self._meta_cache[dataset_id]

        index_path = self._index_path(dataset_id)
        meta_path = self._meta_path(dataset_id)
        if index_path.exists() and meta_path.exists():
            try:
                index = faiss.read_index(str(index_path))
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                self._index_cache[dataset_id] = index
                self._meta_cache[dataset_id] = meta
                return index, meta
            except Exception:
                pass

        count = self.rebuild_dataset_index(db, dataset_id)
        if count == 0:
            return None, None
        return self._index_cache.get(dataset_id), self._meta_cache.get(dataset_id)

    def search(
        self,
        db: Session,
        dataset_ids: list[str],
        query_embedding: list[float],
        *,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        oversample: int = 3,
    ) -> list[tuple[float, str, str]]:
        """跨知识库检索，返回 (similarity, chunk_id, dataset_id)。"""
        if not query_embedding:
            return []

        q = np.array([query_embedding], dtype=np.float32)
        q = self._normalize(q)
        hits: list[tuple[float, str, str]] = []

        for ds_id in dataset_ids:
            index, meta = self._load(db, ds_id)
            if index is None or meta is None:
                continue
            total = int(meta.get("count") or 0)
            if total <= 0:
                continue
            k = min(max(top_k * oversample, top_k), total)
            sims, indices = index.search(q, k)
            chunk_ids: list[str] = meta.get("chunk_ids") or []
            for sim, idx in zip(sims[0], indices[0]):
                if idx < 0 or idx >= len(chunk_ids):
                    continue
                score = float(sim)
                if score < similarity_threshold:
                    continue
                hits.append((score, chunk_ids[int(idx)], ds_id))

        hits.sort(key=lambda x: x[0], reverse=True)
        return hits[:top_k]


vector_index_service = VectorIndexService(settings.data_path)
