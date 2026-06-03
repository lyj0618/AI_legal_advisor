from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser, require_admin
from app.models import User
from app.services.passwords import hash_password
from app.utils import err, format_gmt, new_id, ok

router = APIRouter(prefix="/api/v1/users", tags=["users"], dependencies=[Depends(require_admin)])


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="consultant", pattern="^(admin|consultant)$")


def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "create_date": format_gmt(u.create_date),
    }


@router.get("")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.create_date.desc()).all()
    return ok([_user_dict(u) for u in users])


@router.post("")
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        return err("用户名已存在")
    user = User(
        id=new_id(),
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return ok(_user_dict(user))
