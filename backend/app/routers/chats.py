import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import CurrentUser, require_admin, require_auth
from app.services.chat_access import assert_chat_access, get_config_chat, is_expert_template
from app.models import Chat, ChatDataset, ChatMessage, Dataset
from app.services.builtin_experts import DEFAULT_LEGAL_SYSTEM
from app.services.chat_context import build_chat_messages, finalize_assistant_answer
from app.services.chat_images import analyze_chat_image_content, get_chat_image_path, save_chat_image
from app.services.answer_format import compose_answer
from app.utils import strip_markdown
from app.services.dashscope import dashscope_client
from app.services.qa_cache import (
    find_high_confidence_answer,
    sync_feedback_to_qa,
    upsert_qa_record,
)
from app.utils import format_gmt, new_id, ok, err, parse_json_field, paginate_query, paginated_data

router = APIRouter(prefix="/api/v1", tags=["chats"])


class PromptConfig(BaseModel):
    prompt: str = ""
    opener: str = "您好，我是您的 AI 智能助手，请问有什么可以帮您？"
    empty_response: str = "知识库中未找到相关内容，请补充材料或换个问法。"
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
    question: str = ""
    stream: bool = True
    image_ids: list[str] | None = None


class MessageFeedbackRequest(BaseModel):
    feedback: str | None = None  # like | dislike | null 清除


def _parse_attachments(raw: str | None) -> list[dict]:
    data = parse_json_field(raw or "[]", default=[])
    return data if isinstance(data, list) else []


def _message_dict(m: ChatMessage, chat_id: str | None = None) -> dict:
    attachments = _parse_attachments(m.attachments_json)
    if chat_id:
        for item in attachments:
            if isinstance(item, dict) and item.get("id") and not item.get("url"):
                item["url"] = f"/api/v1/chats/{chat_id}/images/{item['id']}"
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "attachments": attachments,
        "images": parse_json_field(m.images) if m.images else [],
        "feedback": m.feedback,
    }


def _attachments_payload(chat_id: str, image_ids: list[str]) -> str:
    items = [
        {"id": image_id, "url": f"/api/v1/chats/{chat_id}/images/{image_id}"}
        for image_id in image_ids
        if image_id
    ]
    return json.dumps(items, ensure_ascii=False)


def _create_user_message(
    chat_id: str,
    question: str,
    image_ids: list[str] | None = None,
) -> ChatMessage:
    ids = [i for i in (image_ids or []) if i]
    return ChatMessage(
        chat_id=chat_id,
        role="user",
        content=question,
        attachments_json=_attachments_payload(chat_id, ids) if ids else "[]",
    )


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
def list_chats(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
):
    q = (
        db.query(Chat)
        .filter(Chat.owner_username.is_(None), Chat.template_id.is_(None))
        .order_by(Chat.create_date.desc())
    )
    rows, total = paginate_query(q, page, page_size)
    return ok(paginated_data([_chat_dict(c, db) for c in rows], total, page, page_size))


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


@router.get("/chats/{chat_id}/export")
def export_chat(
    chat_id: str,
    fmt: str = Query("md", alias="format"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    assert_chat_access(chat, user)
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.create_date.asc())
        .all()
    )
    lines = [f"# {chat.name}", "", f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for m in msgs:
        role = "用户" if m.role == "user" else "助手"
        lines.append(f"## {role}")
        lines.append("")
        lines.append(m.content or "")
        lines.append("")
    text = "\n".join(lines)
    if fmt == "txt":
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")


@router.post("/chats/{chat_id}/share")
def create_share_link(chat_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    assert_chat_access(chat, user)
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    token = jwt.encode(
        {"chat_id": chat_id, "exp": exp, "typ": "share"},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return ok({"token": token, "expires_at": format_gmt(exp.replace(tzinfo=None)), "path": f"/share/{token}"})


@router.get("/share/{token}")
def read_shared_chat(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return err("分享链接无效或已过期", code=404)
    if payload.get("typ") != "share":
        return err("无效的分享令牌", code=404)
    chat_id = payload.get("chat_id")
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("对话不存在", code=404)
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.create_date.asc())
        .all()
    )
    return ok(
        {
            "name": chat.name,
            "messages": [{"role": m.role, "content": m.content} for m in msgs],
        }
    )


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
    return ok([_message_dict(m, chat_id) for m in msgs])


@router.post("/chats/{chat_id}/messages/{message_id}/feedback")
def set_message_feedback(
    chat_id: str,
    message_id: int,
    body: MessageFeedbackRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    assert_chat_access(chat, user)
    msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == message_id, ChatMessage.chat_id == chat_id)
        .first()
    )
    if not msg:
        return err("消息不存在", code=404)
    if msg.role != "assistant":
        return err("仅可对助手回复评价")
    if body.feedback is not None and body.feedback not in ("like", "dislike"):
        return err("无效的评价类型")
    msg.feedback = body.feedback
    db.commit()
    sync_feedback_to_qa(db, message_id, body.feedback)
    return ok(_message_dict(msg, chat_id))


@router.post("/chats/{chat_id}/images")
async def upload_chat_image(
    chat_id: str,
    file: UploadFile = File(...),
    analyze: bool = Query(True, description="上传后自动解析图片内容"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    assert_chat_access(chat, user)
    data = await file.read()
    try:
        saved = save_chat_image(chat_id, file, data)
    except ValueError as e:
        return err(str(e))
    payload = {
        "id": saved["id"],
        "name": saved["name"],
        "url": f"/api/v1/chats/{chat_id}/images/{saved['id']}",
        "analysis": "",
    }
    if analyze:
        try:
            payload["analysis"] = await analyze_chat_image_content(Path(saved["path"]))
        except Exception as e:
            payload["analysis_error"] = str(e)
    return ok(payload, message="图片上传成功")


@router.get("/chats/{chat_id}/images/{image_id}")
def get_chat_image(
    chat_id: str,
    image_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在", code=404)
    assert_chat_access(chat, user)
    path = get_chat_image_path(chat_id, image_id)
    if not path:
        return err("图片不存在", code=404)
    return FileResponse(path)


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_cached_answer(chat_id: str, question: str, cached_answer: str, db: Session, doc_images: list[str] | None = None):
    db.add(ChatMessage(chat_id=chat_id, role="user", content=question))
    db.commit()
    chunk_size = 24
    for i in range(0, len(cached_answer), chunk_size):
        yield _sse_event({"type": "delta", "content": cached_answer[i : i + chunk_size]})
    assistant_msg = ChatMessage(chat_id=chat_id, role="assistant", content=cached_answer)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat:
        await upsert_qa_record(
            db,
            chat=chat,
            question=question,
            answer=cached_answer,
            assistant_message_id=assistant_msg.id,
            doc_images=doc_images,
        )
    yield _sse_event(
        {
            "type": "done",
            "answer": cached_answer,
            "message_id": assistant_msg.id,
            "from_cache": True,
            "doc_images": doc_images or [],
        }
    )


@router.post("/chats/{chat_id}/completions")
async def chat_completion(
    chat_id: str, body: CompletionRequest, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return err("聊天不存在")
    assert_chat_access(chat, user)
    if is_expert_template(chat) and not user.is_admin:
        return err("请从助手广场进入咨询")

    question = body.question.strip()
    image_ids = [i.strip() for i in (body.image_ids or []) if i and i.strip()]
    if len(image_ids) > settings.max_chat_images:
        return err(f"最多上传 {settings.max_chat_images} 张图片")
    if not question and not image_ids:
        return err("请输入问题或上传图片")

    use_cache = not image_ids
    cached = await find_high_confidence_answer(db, chat, question) if use_cache and question else None
    if cached:
        answer = compose_answer(strip_markdown(cached.answer), "")
        cached_doc_images = json.loads(cached.doc_images or "[]") if cached.doc_images else []
        if not body.stream:
            db.add(_create_user_message(chat_id, question, image_ids))
            assistant_msg = ChatMessage(chat_id=chat_id, role="assistant", content=answer)
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)
            await upsert_qa_record(
                db,
                chat=chat,
                question=question,
                answer=answer,
                assistant_message_id=assistant_msg.id,
                doc_images=cached_doc_images,
            )
            return ok({"answer": answer, "message_id": assistant_msg.id, "from_cache": True, "doc_images": cached_doc_images})

        return StreamingResponse(
            _stream_cached_answer(chat_id, question, answer, db, cached_doc_images),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        messages, sources_body, doc_image_urls = await build_chat_messages(
            db, chat, question, image_ids=image_ids
        )
    except Exception as e:
        return err(str(e))

    if not body.stream:
        try:
            raw = (await dashscope_client.chat_completion(messages)).rstrip()
            answer = finalize_assistant_answer(raw, sources_body)
        except Exception as e:
            return err(str(e))
        db.add(_create_user_message(chat_id, question, image_ids))
        assistant_msg = ChatMessage(
            chat_id=chat_id,
            role="assistant",
            content=answer,
            images=json.dumps(doc_image_urls, ensure_ascii=False),
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)
        if question:
            await upsert_qa_record(
                db,
                chat=chat,
                question=question,
                answer=answer,
                assistant_message_id=assistant_msg.id,
                doc_images=doc_image_urls,
            )
        return ok({"answer": answer, "message_id": assistant_msg.id, "doc_images": doc_image_urls})

    async def event_generator():
        db.add(_create_user_message(chat_id, question, image_ids))
        db.commit()
        parts: list[str] = []
        try:
            async for token in dashscope_client.chat_completion_stream(messages):
                parts.append(token)
                yield _sse_event({"type": "delta", "content": token})
            answer = finalize_assistant_answer("".join(parts), sources_body)
            assistant_msg = ChatMessage(
                chat_id=chat_id,
                role="assistant",
                content=answer,
                images=json.dumps(doc_image_urls, ensure_ascii=False),
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)
            if question:
                await upsert_qa_record(
                    db,
                    chat=chat,
                    question=question,
                    answer=answer,
                    assistant_message_id=assistant_msg.id,
                    doc_images=doc_image_urls,
                )
            yield _sse_event({"type": "done", "answer": answer, "message_id": assistant_msg.id, "doc_images": doc_image_urls})
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
