from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser, require_auth
from app.models import User
from app.services.auth import authenticate_user, create_access_token
from app.utils import err, ok

DEFAULT_QUESTION_COLOR = "#2563eb"
DEFAULT_ANSWER_COLOR = "#f1f5f9"

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class PreferencesBody(BaseModel):
    question_bubble_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    answer_bubble_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


def _prefs_dict(user: User) -> dict:
    return {
        "question_bubble_color": user.question_bubble_color or DEFAULT_QUESTION_COLOR,
        "answer_bubble_color": user.answer_bubble_color or DEFAULT_ANSWER_COLOR,
    }


def _get_user_row(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.username, body.password)
    if not user:
        return err("用户名或密码错误", code=401)
    token = create_access_token(user.username, user.role)
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "username": user.username,
            "role": user.role,
        }
    )


@router.get("/me")
def me(user: CurrentUser = Depends(require_auth), db: Session = Depends(get_db)):
    row = db.query(User).filter(User.username == user.username).first()
    return ok(
        {
            "username": user.username,
            "role": user.role,
            "question_bubble_color": (row.question_bubble_color if row else None) or DEFAULT_QUESTION_COLOR,
            "answer_bubble_color": (row.answer_bubble_color if row else None) or DEFAULT_ANSWER_COLOR,
        }
    )


@router.get("/preferences")
def get_preferences(
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    row = _get_user_row(db, user.username)
    if not row:
        return ok(
            {
                "question_bubble_color": DEFAULT_QUESTION_COLOR,
                "answer_bubble_color": DEFAULT_ANSWER_COLOR,
            }
        )
    return ok(_prefs_dict(row))


@router.put("/preferences")
def update_preferences(
    body: PreferencesBody,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    row = _get_user_row(db, user.username)
    if not row:
        return err("用户不存在", code=404)
    row.question_bubble_color = body.question_bubble_color
    row.answer_bubble_color = body.answer_bubble_color
    db.commit()
    return ok(_prefs_dict(row))


@router.post("/logout")
def logout(user: CurrentUser = Depends(require_auth)):
    return ok({"message": "已退出"})
