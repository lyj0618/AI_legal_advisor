from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.services.passwords import hash_password
from app.utils import new_id


def ensure_default_admin(db: Session) -> None:
    admin = db.query(User).filter(User.username == settings.auth_username).first()
    if admin:
        return
    db.add(
        User(
            id=new_id(),
            username=settings.auth_username,
            password_hash=hash_password(settings.auth_password),
            role="admin",
            is_active=True,
        )
    )
    db.commit()
