from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser, require_admin
from app.models import User
from app.services.passwords import hash_password
from app.utils import err, format_gmt, new_id, ok, paginate_query, paginated_data

router = APIRouter(prefix="/api/v1/users", tags=["users"], dependencies=[Depends(require_admin)])


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="consultant", pattern="^(admin|consultant)$")


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = Field(default=None, pattern="^(admin|consultant)$")
    is_active: bool | None = None


def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "create_date": format_gmt(u.create_date),
    }


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
):
    q = db.query(User).order_by(User.create_date.desc())
    rows, total = paginate_query(q, page, page_size)
    return ok(paginated_data([_user_dict(u) for u in rows], total, page, page_size))


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


def _count_admins(db: Session) -> int:
    return db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()


@router.put("/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return err("用户不存在", code=404)

    if body.role is not None and body.role != user.role:
        if user.role == "admin" and body.role != "admin" and _count_admins(db) <= 1:
            return err("不能修改唯一管理员的角色")
        user.role = body.role

    if body.is_active is not None:
        if user.username == current.username and not body.is_active:
            return err("不能禁用当前登录账号")
        if user.role == "admin" and not body.is_active and _count_admins(db) <= 1:
            return err("不能禁用唯一管理员")
        user.is_active = body.is_active

    if body.password:
        user.password_hash = hash_password(body.password)

    db.commit()
    return ok(_user_dict(user))


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return err("用户不存在", code=404)
    if user.username == current.username:
        return err("不能删除当前登录账号")
    if user.role == "admin" and _count_admins(db) <= 1:
        return err("不能删除唯一管理员")
    db.delete(user)
    db.commit()
    return ok()
