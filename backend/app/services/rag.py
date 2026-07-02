import json
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Dataset, Document
from app.services.dashscope import dashscope_client
from app.services.vector_index import vector_index_service


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


async def _retrieve_brute_force(
    db: Session,
    dataset_ids: list[str],
    q_emb: list[float],
    top_k: int,
    similarity_threshold: float,
) -> list[dict[str, Any]]:
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


async def _retrieve_with_index(
    db: Session,
    dataset_ids: list[str],
    q_emb: list[float],
    top_k: int,
    similarity_threshold: float,
) -> list[dict[str, Any]]:
    hits = vector_index_service.search(
        db,
        dataset_ids,
        q_emb,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )
    if not hits:
        return []

    chunk_ids = [h[1] for h in hits]
    chunk_rows = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    chunk_map = {c.id: c for c in chunk_rows}

    ds_map: dict[str, Dataset] = {}
    doc_map: dict[str, Document] = {}
    results: list[dict[str, Any]] = []

    for sim, chunk_id, ds_id in hits:
        ch = chunk_map.get(chunk_id)
        if not ch or not ch.available:
            continue
        if ds_id not in ds_map:
            ds = db.query(Dataset).filter(Dataset.id == ds_id).first()
            if ds:
                ds_map[ds_id] = ds
        if ch.document_id not in doc_map:
            doc = db.query(Document).filter(Document.id == ch.document_id).first()
            if doc and doc.status == "1":
                doc_map[ch.document_id] = doc
            else:
                continue
        doc = doc_map.get(ch.document_id)
        ds = ds_map.get(ds_id)
        results.append(
            {
                "content": ch.content,
                "similarity": sim,
                "doc_name": doc.name if doc else "",
                "dataset_id": ds_id,
                "dataset_name": ds.name if ds else "",
            }
        )
    return results


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

    if settings.use_vector_index:
        try:
            indexed = await _retrieve_with_index(
                db, dataset_ids, q_emb, top_k, similarity_threshold
            )
            if indexed:
                return indexed
        except Exception:
            pass

    return await _retrieve_brute_force(
        db, dataset_ids, q_emb, top_k, similarity_threshold
    )


def build_knowledge_context(chunks: list[dict[str, Any]], *, min_sim: float = 0.28) -> str:
    if not chunks:
        return ""
    ranked = sorted(chunks, key=lambda x: float(x.get("similarity") or 0), reverse=True)
    filtered = [c for c in ranked if float(c.get("similarity") or 0) >= min_sim]
    use = filtered if filtered else ranked[:3]
    lines = []
    for i, c in enumerate(use, 1):
        src = c.get("doc_name") or "未知文档"
        kb = c.get("dataset_name") or ""
        prefix = f"{kb} / " if kb else ""
        lines.append(f"[{i}] 来源：{prefix}{src}\n{c.get('content', '')}")
    return "\n\n".join(lines)


SOURCE_DISPLAY_MIN_SIM = 0.35


def format_answer_sources_body(chunks: list[dict[str, Any]], *, has_kb: bool) -> str:
    """生成「回答依据出处」节正文（不含标题）。"""
    if not has_kb:
        return "本助手未绑定知识库，以上内容基于模型通用知识生成，仅供参考；重要事项请核实原始资料或咨询专业人士。"
    if not chunks:
        return "本次未在知识库中检索到与您问题高度相关的条目，以上内容结合模型知识生成，仅供参考；请补充资料或调整问法后重试。"

    ranked = sorted(chunks, key=lambda x: float(x.get("similarity") or 0), reverse=True)
    top_sim = float(ranked[0].get("similarity") or 0)
    display = [c for c in ranked if float(c.get("similarity") or 0) >= SOURCE_DISPLAY_MIN_SIM]

    if not display:
        return (
            f"已检索知识库，最高相关度约为 {top_sim:.0%}，未发现与您问题直接相关的制度条文。"
            "请勿将低相关检索结果当作结论依据；建议补充制度名称或向主管部门核实。"
        )

    lines: list[str] = []
    for i, c in enumerate(display, 1):
        doc = c.get("doc_name") or "未知文档"
        kb = c.get("dataset_name") or ""
        sim = float(c.get("similarity") or 0)
        raw = (c.get("content") or "").strip().replace("\n", " ")
        excerpt = raw[:150] + ("…" if len(raw) > 150 else "")
        loc = f"知识库「{kb}」" if kb else "知识库"
        lines.append(f"{i}. {loc} · 文档《{doc}》（相关度 {sim:.0%}）\n   {excerpt}")
    lines.append("\n以上内容摘自知识库片段，仅供参考。")
    return "\n".join(lines)


def format_answer_sources(chunks: list[dict[str, Any]], *, has_kb: bool) -> str:
    """兼容旧调用：带标题的完整出处段落。"""
    body = format_answer_sources_body(chunks, has_kb=has_kb)
    return f"\n\n---\n回答依据出处\n{body}" if body else ""
