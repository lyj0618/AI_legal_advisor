from sqlalchemy.orm import Session

from app.models import Chat, ChatMessage
from app.services.chat_access import get_config_chat, get_kb_dataset_ids
from app.services.builtin_experts import DEFAULT_LEGAL_SYSTEM
from app.services.rag import build_knowledge_context, format_answer_sources, retrieve
from app.utils import parse_json_field


async def build_chat_messages(db: Session, chat: Chat, question: str) -> tuple[list[dict[str, str]], str]:
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
    sources_suffix = format_answer_sources(chunks, has_kb=bool(kb_ids))

    system_tpl = prompt_cfg.get("prompt") or DEFAULT_LEGAL_SYSTEM
    if "{knowledge}" in system_tpl:
        system_content = system_tpl.replace("{knowledge}", knowledge or "（暂无匹配知识库内容）")
    else:
        system_content = system_tpl + "\n\n" + (knowledge or "")

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.create_date.asc())
        .limit(20)
        .all()
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": question})
    return messages, sources_suffix
