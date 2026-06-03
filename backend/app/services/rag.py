import json
import math
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models import Chunk, Dataset, Document
from app.services.dashscope import dashscope_client


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


async def retrieve(
    db: Session,
    dataset_ids: list[str],
    question: str,
    top_k: int = 5,
    similarity_threshold: float = 0.2,
) -> list[dict[str, Any]]:
    if not question.strip():
        return []

    q_emb = (await dashscope_client.embed_texts([question]))[0]
    results: list[dict[str, Any]] = []

    for ds_id in dataset_ids:
        ds = db.query(Dataset).filter(Dataset.id == ds_id).first()
        if not ds:
            continue
        docs = db.query(Document).filter(Document.dataset_id == ds_id, Document.status == "1").all()
        doc_map = {d.id: d for d in docs}
        doc_ids = list(doc_map.keys())
        if not doc_ids:
            continue

        chunks = (
            db.query(Chunk)
            .filter(Chunk.document_id.in_(doc_ids), Chunk.available.is_(True))
            .all()
        )
        for ch in chunks:
            if not ch.embedding:
                continue
            try:
                emb = json.loads(ch.embedding)
            except json.JSONDecodeError:
                continue
            sim = _cosine(q_emb, emb)
            if sim < similarity_threshold:
                continue
            doc = doc_map.get(ch.document_id)
            results.append(
                {
                    "content": ch.content,
                    "similarity": sim,
                    "doc_name": doc.name if doc else "",
                    "dataset_id": ds_id,
                    "dataset_name": ds.name if ds else "",
                }
            )

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def build_knowledge_context(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return ""
    lines = []
    for i, c in enumerate(chunks, 1):
        src = c.get("doc_name") or "未知文档"
        kb = c.get("dataset_name") or ""
        prefix = f"{kb} / " if kb else ""
        lines.append(f"[{i}] 来源：{prefix}{src}\n{c.get('content', '')}")
    return "\n\n".join(lines)


def format_answer_sources(chunks: list[dict[str, Any]], *, has_kb: bool) -> str:
    """生成附在回答正文之后的依据出处说明。"""
    header = "\n\n---\n**回答依据出处**\n"
    if not has_kb:
        return (
            header
            + "\n本助手未绑定法律知识库，以上内容基于模型对中国法律法规的通用理解，仅供参考，不构成正式法律意见；重大事项请咨询执业律师。"
        )
    if not chunks:
        return (
            header
            + "\n本次未在知识库中检索到与您问题高度相关的条目，以上内容结合模型法律知识生成，仅供参考；请补充制度/合同等材料或调整问法后重试。"
        )

    lines = [header]
    for i, c in enumerate(chunks, 1):
        doc = c.get("doc_name") or "未知文档"
        kb = c.get("dataset_name") or ""
        sim = float(c.get("similarity") or 0)
        raw = (c.get("content") or "").strip().replace("\n", " ")
        excerpt = raw[:150] + ("…" if len(raw) > 150 else "")
        loc = f"知识库「{kb}」" if kb else "知识库"
        lines.append(f"\n{i}. {loc} · 文档《{doc}》（相关度 {sim:.0%}）\n   > {excerpt}")
    lines.append("\n\n*以上内容摘自知识库片段，仅供参考，不构成正式法律意见。*")
    return "".join(lines)
