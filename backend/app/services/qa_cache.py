"""问答对缓存：高置信度命中时直接返回已存储答案。"""
from __future__ import annotations

import json
import re
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models import Chat, ChatMessage, QaRecord
from app.services.chat_access import is_expert_template
from app.services.dashscope import dashscope_client
from app.utils import format_gmt, new_id

SIMILARITY_THRESHOLD = 0.92


def normalize_question(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "", s)
    return s[:500]


def resolve_template_id(chat: Chat | None) -> str | None:
    if not chat:
        return None
    if chat.template_id:
        return chat.template_id
    if is_expert_template(chat):
        return chat.id
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def qa_record_dict(r: QaRecord, *, chat_name: str = "") -> dict[str, Any]:
    adoption = "未评价"
    if r.feedback == "like":
        adoption = "已采纳"
    elif r.feedback == "dislike":
        adoption = "未采纳"
    return {
        "id": r.id,
        "template_id": r.template_id,
        "chat_id": r.chat_id,
        "chat_name": chat_name,
        "assistant_message_id": r.assistant_message_id,
        "question": r.question,
        "answer": r.answer,
        "confidence": r.confidence or "low",
        "feedback": r.feedback,
        "adoption": adoption,
        "hit_count": r.hit_count or 0,
        "create_date": format_gmt(r.create_date),
        "update_date": format_gmt(r.update_date),
    }


async def find_high_confidence_answer(
    db: Session,
    chat: Chat,
    question: str,
) -> QaRecord | None:
    template_id = resolve_template_id(chat)
    if not template_id:
        return None

    norm = normalize_question(question)
    if not norm:
        return None

    exact = (
        db.query(QaRecord)
        .filter(
            QaRecord.template_id == template_id,
            QaRecord.confidence == "high",
            QaRecord.question_norm == norm,
        )
        .first()
    )
    if exact:
        exact.hit_count = (exact.hit_count or 0) + 1
        db.commit()
        return exact

    try:
        q_emb = (await dashscope_client.embed_texts([question]))[0]
    except Exception:
        return None

    candidates = (
        db.query(QaRecord)
        .filter(QaRecord.template_id == template_id, QaRecord.confidence == "high")
        .all()
    )
    best: QaRecord | None = None
    best_sim = 0.0
    for rec in candidates:
        if not rec.question_embedding:
            continue
        try:
            emb = json.loads(rec.question_embedding)
        except json.JSONDecodeError:
            continue
        sim = _cosine(q_emb, emb)
        if sim > best_sim:
            best_sim = sim
            best = rec

    if best and best_sim >= SIMILARITY_THRESHOLD:
        best.hit_count = (best.hit_count or 0) + 1
        db.commit()
        return best
    return None


async def upsert_qa_record(
    db: Session,
    *,
    chat: Chat,
    question: str,
    answer: str,
    assistant_message_id: int | None,
    doc_images: list[str] | None = None,
) -> QaRecord:
    template_id = resolve_template_id(chat)
    norm = normalize_question(question)
    doc_images_json = json.dumps(doc_images or [], ensure_ascii=False)

    existing: QaRecord | None = None
    if assistant_message_id:
        existing = (
            db.query(QaRecord)
            .filter(QaRecord.assistant_message_id == assistant_message_id)
            .first()
        )

    embedding_json = ""
    try:
        emb = (await dashscope_client.embed_texts([question]))[0]
        embedding_json = json.dumps(emb, ensure_ascii=False)
    except Exception:
        pass

    if existing:
        existing.question = question
        existing.question_norm = norm
        existing.answer = answer
        existing.template_id = template_id
        existing.chat_id = chat.id
        existing.doc_images = doc_images_json
        if embedding_json:
            existing.question_embedding = embedding_json
        db.commit()
        return existing

    rec = QaRecord(
        id=new_id(),
        template_id=template_id,
        chat_id=chat.id,
        assistant_message_id=assistant_message_id,
        question=question,
        question_norm=norm,
        answer=answer,
        confidence="low",
        doc_images=doc_images_json,
        question_embedding=embedding_json,
    )
    db.add(rec)
    db.commit()
    return rec


def sync_feedback_to_qa(db: Session, assistant_message_id: int, feedback: str | None) -> None:
    rec = (
        db.query(QaRecord)
        .filter(QaRecord.assistant_message_id == assistant_message_id)
        .first()
    )
    if rec:
        rec.feedback = feedback
        db.commit()


def sync_from_chat_messages(db: Session) -> int:
    """从历史消息同步问答对，返回新增条数。"""
    added = 0
    chats = db.query(Chat).filter(Chat.owner_username.isnot(None)).all()
    for chat in chats:
        msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat.id)
            .order_by(ChatMessage.create_date.asc())
            .all()
        )
        i = 0
        while i < len(msgs) - 1:
            user_m, asst_m = msgs[i], msgs[i + 1]
            if user_m.role == "user" and asst_m.role == "assistant":
                exists = (
                    db.query(QaRecord)
                    .filter(QaRecord.assistant_message_id == asst_m.id)
                    .first()
                )
                if not exists and (user_m.content or "").strip() and (asst_m.content or "").strip():
                    rec = QaRecord(
                        id=new_id(),
                        template_id=resolve_template_id(chat),
                        chat_id=chat.id,
                        assistant_message_id=asst_m.id,
                        question=user_m.content,
                        question_norm=normalize_question(user_m.content),
                        answer=asst_m.content,
                        confidence="low",
                        feedback=asst_m.feedback,
                    )
                    db.add(rec)
                    added += 1
                i += 2
            else:
                i += 1
    if added:
        db.commit()
    return added
