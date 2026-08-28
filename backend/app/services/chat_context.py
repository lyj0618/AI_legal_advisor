import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import Chat, ChatMessage
from app.services.chat_access import get_config_chat, get_kb_dataset_ids
from app.services.answer_format import ANSWER_FORMAT_INSTRUCTION, compose_answer
from app.services.builtin_experts import DEFAULT_LEGAL_SYSTEM
from app.services.chat_images import build_user_message_content, resolve_image_data_urls
from app.services.rag import build_knowledge_context, format_answer_sources_body, retrieve
from app.utils import parse_json_field

IMAGE_ANSWER_HINT = """

【图片解读】用户可能上传了图片。请先仔细识别图片中的文字、表格、印章、签名及关键要素，再结合知识库内容作答；若图片与知识库无关，请基于图片可见信息给出客观分析。"""


def finalize_assistant_answer(llm_text: str, sources_body: str = "") -> str:
    return compose_answer(llm_text, sources_body)


def _parse_attachments(raw: str | None) -> list[dict]:
    data = parse_json_field(raw or "[]", default=[])
    return data if isinstance(data, list) else []


def _history_message_content(m: ChatMessage, chat_id: str) -> str | list[dict[str, Any]]:
    attachments = _parse_attachments(m.attachments_json)
    image_ids = [a.get("id") for a in attachments if isinstance(a, dict) and a.get("id")]
    image_urls = resolve_image_data_urls(chat_id, image_ids) if image_ids else []
    return build_user_message_content(m.content, image_urls)


async def build_chat_messages(
    db: Session,
    chat: Chat,
    question: str,
    *,
    image_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    cfg_chat = get_config_chat(db, chat)
    prompt_cfg = parse_json_field(cfg_chat.prompt_config)
    kb_ids = get_kb_dataset_ids(db, chat)

    chunks: list = []
    if kb_ids:
        chunks = await retrieve(
            db,
            kb_ids,
            question,
            top_k=int(prompt_cfg.get("top_n", 8)),
            similarity_threshold=float(prompt_cfg.get("similarity_threshold", 0.2)),
        )
    knowledge = build_knowledge_context(chunks)
    sources_body = format_answer_sources_body(chunks, has_kb=bool(kb_ids))

    # 收集检索命中分块所引用的文档内嵌图片 URL（顺序、去重）
    doc_image_urls: list[str] = []
    for c in chunks:
        for u in (c.get("images") or []):
            if u and u not in doc_image_urls:
                doc_image_urls.append(u)

    system_tpl = prompt_cfg.get("prompt") or DEFAULT_LEGAL_SYSTEM
    if "{knowledge}" in system_tpl:
        system_content = system_tpl.replace("{knowledge}", knowledge or "（暂无匹配知识库内容）")
    else:
        system_content = system_tpl + "\n\n" + (knowledge or "")

    if "【回答版式】" not in system_content:
        system_content = system_content.rstrip() + ANSWER_FORMAT_INSTRUCTION

    # 若命中知识库截图，提示模型优先依据截图内容作答
    if doc_image_urls and "【知识库截图】" not in system_content:
        system_content = (
            system_content.rstrip()
            + "\n\n【知识库截图】本次检索命中的知识库片段包含配图（截图），"
            "请在回答中引用截图中的关键表格、界面与流程信息；如需在回复中展示截图，"
            "使用约定占位（前端会据此渲染）。"
        )

    image_data_urls = resolve_image_data_urls(chat.id, image_ids or [])
    if image_data_urls and "【图片解读】" not in system_content:
        system_content = system_content.rstrip() + IMAGE_ANSWER_HINT

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.create_date.asc())
        .limit(20)
        .all()
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
    for m in history:
        if m.role == "user" and _parse_attachments(m.attachments_json):
            messages.append({"role": m.role, "content": _history_message_content(m, chat.id)})
        else:
            messages.append({"role": m.role, "content": m.content})
    messages.append(
        {
            "role": "user",
            "content": build_user_message_content(question, image_data_urls),
        }
    )
    return messages, sources_body, doc_image_urls
