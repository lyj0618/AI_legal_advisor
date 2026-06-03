from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser
from app.models import Chat, ChatDataset


def is_expert_template(chat: Chat | None) -> bool:
    return chat is not None and chat.owner_username is None and chat.template_id is None


def assert_chat_access(chat: Chat | None, user: CurrentUser) -> Chat:
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    if user.is_admin:
        return chat
    if chat.owner_username != user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此对话")
    return chat


def get_config_chat(db: Session, chat: Chat) -> Chat:
    if chat.template_id:
        template = db.query(Chat).filter(Chat.id == chat.template_id).first()
        if template:
            return template
    return chat


def get_kb_dataset_ids(db: Session, chat: Chat) -> list[str]:
    cfg = get_config_chat(db, chat)
    links = db.query(ChatDataset).filter(ChatDataset.chat_id == cfg.id).all()
    return [link.dataset_id for link in links]


def template_has_kb(db: Session, template_id: str) -> bool:
    return (
        db.query(ChatDataset).filter(ChatDataset.chat_id == template_id).count() > 0
    )
