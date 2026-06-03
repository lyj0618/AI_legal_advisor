from sqlalchemy.orm import Session

from app.models import Chat
from app.services.builtin_experts import BUILTIN_EXPERTS
from app.utils import new_id


def ensure_builtin_expert_templates(db: Session) -> None:
    for e in BUILTIN_EXPERTS:
        exists = (
            db.query(Chat)
            .filter(Chat.builtin_expert_id == e["id"], Chat.owner_username.is_(None))
            .first()
        )
        if exists:
            continue
        db.add(
            Chat(
                id=new_id(),
                name=e["name"],
                description=e["desc"],
                expert_role=e["role"],
                color=e.get("color", "#2563eb"),
                builtin_expert_id=e["id"],
                owner_username=None,
                template_id=None,
                is_published=False,
                prompt_config="{}",
            )
        )
    db.commit()
