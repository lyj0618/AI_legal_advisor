import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser, require_auth
from app.models import Chat, ChatDataset, Dataset
from app.services.builtin_experts import DEFAULT_LEGAL_SYSTEM
from app.services.chat_access import assert_chat_access, is_expert_template, template_has_kb
from app.utils import new_id, ok, err, parse_json_field

router = APIRouter(prefix="/api/v1", tags=["experts"], dependencies=[Depends(require_auth)])

CHAT_COLORS = ["#0ea5e9", "#8b5cf6", "#ec4899", "#14b8a6", "#f59e0b", "#6366f1", "#84cc16", "#f43f5e"]


def _template_dict(chat: Chat, db: Session, *, include_publish: bool) -> dict:
    kb_names = []
    for link in db.query(ChatDataset).filter(ChatDataset.chat_id == chat.id).all():
        ds = db.query(Dataset).filter(Dataset.id == link.dataset_id).first()
        if ds:
            kb_names.append(ds.name)
    item = {
        "id": chat.id,
        "name": chat.name,
        "role": chat.expert_role or "法律顾问",
        "desc": chat.description or f"已绑定：{', '.join(kb_names)}",
        "color": chat.color or CHAT_COLORS[0],
        "avatarFile": "__chat__",
        "_type": "template",
        "_chatId": chat.id,
        "chat_id": chat.id,
        "kb_names": kb_names,
    }
    if include_publish:
        item["is_published"] = bool(chat.is_published)
    return item


@router.get("/experts")
def list_experts(db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)):
    templates = (
        db.query(Chat)
        .filter(Chat.owner_username.is_(None), Chat.template_id.is_(None))
        .order_by(Chat.create_date.asc())
        .all()
    )
    experts = []
    color_idx = 0
    for chat in templates:
        if not template_has_kb(db, chat.id):
            continue
        if not user.is_admin and not chat.is_published:
            continue
        item = _template_dict(chat, db, include_publish=user.is_admin)
        if not item.get("color"):
            item["color"] = CHAT_COLORS[color_idx % len(CHAT_COLORS)]
        experts.append(item)
        color_idx += 1
    return ok(experts)


def _resolve_template(db: Session, template_id: str) -> Chat | None:
    tid = template_id[5:] if template_id.startswith("chat_") else template_id
    chat = db.query(Chat).filter(Chat.id == tid).first()
    if is_expert_template(chat):
        return chat
    chat = (
        db.query(Chat)
        .filter(
            Chat.builtin_expert_id == tid,
            Chat.owner_username.is_(None),
            Chat.template_id.is_(None),
        )
        .first()
    )
    if is_expert_template(chat):
        return chat
    return None


@router.post("/experts/{template_id}/consult")
def start_consult(
    template_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    template = _resolve_template(db, template_id)
    if not template:
        return err("专家不存在", code=404)
    template_id = template.id
    if not template_has_kb(db, template_id):
        return err("该专家尚未关联知识库，暂不可咨询")
    if not user.is_admin and not template.is_published:
        return err("该专家尚未发布")

    session = (
        db.query(Chat)
        .filter(Chat.template_id == template_id, Chat.owner_username == user.username)
        .first()
    )
    if session:
        return ok({"session_id": session.id, "template_id": template_id})

    prompt = parse_json_field(template.prompt_config)
    if not prompt.get("prompt"):
        prompt["prompt"] = DEFAULT_LEGAL_SYSTEM
    if not prompt.get("variables"):
        prompt["variables"] = [{"key": "knowledge", "optional": True}]
    if not prompt.get("opener"):
        prompt["opener"] = (
            f"您好，我是{template.name}，专注{template.expert_role or '法律咨询'}。"
            "请问有什么法律问题需要咨询？"
        )

    session = Chat(
        id=new_id(),
        name=template.name,
        description=template.description,
        expert_role=template.expert_role,
        color=template.color,
        owner_username=user.username,
        template_id=template_id,
        is_published=False,
        prompt_config=json.dumps(prompt, ensure_ascii=False),
        top_k=template.top_k,
    )
    db.add(session)
    db.commit()
    return ok({"session_id": session.id, "template_id": template_id})
