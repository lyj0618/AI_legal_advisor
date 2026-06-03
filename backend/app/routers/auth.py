from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser, require_auth
from app.services.auth import authenticate_user, create_access_token
from app.utils import err, ok

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


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
def me(user: CurrentUser = Depends(require_auth)):
    return ok({"username": user.username, "role": user.role})


@router.post("/logout")
def logout(user: CurrentUser = Depends(require_auth)):
    return ok({"message": "已退出"})
