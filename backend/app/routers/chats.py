import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser, require_admin, require_auth
from app.services.chat_access import assert_chat_access, get_config_chat, is_expert_template
from app.models import Chat, ChatDataset, ChatMessage, Dataset
from app.services.builtin_experts import DEFAULT_LEGAL_SYSTEM
from app.services.chat_context import build_chat_messages
from app.services.dashscope import dashscope_client
from app.utils import format_gmt, new_id, ok, err, parse_json_field

router = APIRouter(prefix="/api/v1", tags=["chats"])


class PromptConfig(BaseModel):
    prompt: str = ""
    opener: str = "您好，我是您的 AI 法律顾问助手，请问有什么法律问题需要咨询？"
    empty_response: str = "知识库中未找到相关法律条文或制度内容，请补充材料或换个问法。"
    variables: list[dict] | None = None
    top_n: int = 8
    similarity_threshold: float = 0.2
    show_quote: bool = False
    keyword: bool = False
    tts: bool = False
    toc_enhance: bool = False


class ChatCreate(BaseModel):
    name: str
    description: str = ""
    expert_role: str = ""
    kb_ids: list[str] | None = None
    prompt: PromptConfig | None = None


class ChatUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    expert_role: str | None = None
    kb_ids: list[str] | None = None
    top_k: int | None = None
    prompt: dict | None = None
    is_published: bool | None = None
    color: str | None = None


class DeleteIds(BaseModel):
    ids: list[str]


class CompletionRequest(BaseModel):
    question: str
    stream: bool = True


def _chat_dict(chat: Chat, db: Session) -> dict:
    cfg = get_config_chat(db, chat)
    links = db.query(ChatDataset).filter(ChatDataset.chat_id == cfg.id).all()
    datasets = []
    for link in links:
        ds = db.query(Dataset).filter(Dataset.id == link.dataset_id).first()
        if ds:
            datasets.append({"id": ds.id, "name": ds.name})
    p = parse_json_field(chat.prompt_config)
    return {
        "id": chat.id,
        "name": chat.name,
        "description": chat.description,
        "expert_role": chat.expert_role,
        "color": chat.color,
        "datasets": datasets,
        "prompt": p,
        "top_k": chat.top_k,
        "is_published": bool(chat.is_published),
        "is_template": is_expert_template(chat),
        "template_id": chat.template_id,
        "owner_username": chat.owner_username,
        "create_date": format_gmt(chat.create_date),
    }


@router.get("/chats/{chat_id}")
def get_chat(chat_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    assert_chat_access(chat, user)
    return ok(_chat_dict(chat, db))


@router.get("/chats")
def list_chats(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    chats = (
        db.query(Chat)
        .filter(Chat.owner_username.is_(None), Chat.template_id.is_(None))
        .order_by(Chat.create_date.desc())
        .all()
    )
    return ok([_chat_dict(c, db) for c in chats])


@router.post("/chats")
def create_chat(body: ChatCreate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    prompt = body.prompt.model_dump() if body.prompt else {}
    if not prompt.get("prompt"):
        prompt["prompt"] = DEFAULT_LEGAL_SYSTEM
    if not prompt.get("variables"):
        prompt["variables"] = [{"key": "knowledge", "optional": True}]

    chat = Chat(
        id=new_id(),
        name=body.name,
        description=body.description,
        expert_role=body.expert_role,
        owner_username=None,
        template_id=None,
        is_published=False,
        prompt_config=json.dumps(prompt, ensure_ascii=False),
    )
    db.add(chat)
    db.flush()

    for kb_id in body.kb_ids or []:
        if db.query(Dataset).filter(Dataset.id == kb_id).first():
            db.add(ChatDataset(chat_id=chat.id, dataset_id=kb_id))

    db.commit()
    return ok(_chat_dict(chat, db))


@router.put("/chats/{chat_id}")
def update_chat(chat_id: str, body: ChatUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    if body.name is not None:
        chat.name = body.name
    if body.description is not None:
        chat.description = body.description
    if body.expert_role is not None:
        chat.expert_role = body.expert_role
    if body.top_k is not None:
        chat.top_k = body.top_k
    if body.prompt is not None:
        old = parse_json_field(chat.prompt_config)
        old.update(body.prompt)
        chat.prompt_config = json.dumps(old, ensure_ascii=False)
    if body.is_published is not None:
        if not is_expert_template(chat):
            return err("仅专家模板可设置发布状态")
        chat.is_published = body.is_published
    if body.color is not None:
        chat.color = body.color
    if body.kb_ids is not None:
        db.query(ChatDataset).filter(ChatDataset.chat_id == chat_id).delete()
        for kb_id in body.kb_ids:
            if db.query(Dataset).filter(Dataset.id == kb_id).first():
                db.add(ChatDataset(chat_id=chat_id, dataset_id=kb_id))
    db.commit()
    return ok(_chat_dict(chat, db))


@router.delete("/chats")
def delete_chats(body: DeleteIds, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    for cid in body.ids:
        chat = db.query(Chat).filter(Chat.id == cid).first()
        if chat:
            db.delete(chat)
    db.commit()
    return ok()


@router.get("/chats/{chat_id}/messages")
def list_messages(chat_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    assert_chat_access(chat, user)
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.create_date.asc())
        .all()
    )
    return ok([{"role": m.role, "content": m.content} for m in msgs])


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chats/{chat_id}/completions")
async def chat_completion(
    chat_id: str, body: CompletionRequest, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    assert_chat_access(chat, user)
    if is_expert_template(chat) and not user.is_admin:
        return err("请从法律顾问团进入咨询")

    question = body.question.strip()
    if not question:
        return err("请输入问题")

    try:
        messages, sources_suffix = await build_chat_messages(db, chat, question)
    except Exception as e:
        return err(str(e))

    if not body.stream:
        try:
            answer = (await dashscope_client.chat_completion(messages)).rstrip() + sources_suffix
        except Exception as e:
            return err(str(e))
        db.add(ChatMessage(chat_id=chat_id, role="user", content=question))
        db.add(ChatMessage(chat_id=chat_id, role="assistant", content=answer))
        db.commit()
        return ok({"answer": answer})

    async def event_generator():
        db.add(ChatMessage(chat_id=chat_id, role="user", content=question))
        db.commit()
        parts: list[str] = []
        try:
            async for token in dashscope_client.chat_completion_stream(messages):
                parts.append(token)
                yield _sse_event({"type": "delta", "content": token})
            if sources_suffix:
                parts.append(sources_suffix)
                yield _sse_event({"type": "delta", "content": sources_suffix})
            answer = "".join(parts)
            db.add(ChatMessage(chat_id=chat_id, role="assistant", content=answer))
            db.commit()
            yield _sse_event({"type": "done", "answer": answer})
        except Exception as e:
            yield _sse_event({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
