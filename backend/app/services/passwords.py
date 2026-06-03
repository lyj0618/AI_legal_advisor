import hashlib
import secrets

from app.config import settings


def hash_password(password: str) -> str:
    salt = settings.jwt_secret[:16]
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"sha256${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    expected = hash_password(password)
    return secrets.compare_digest(expected, password_hash)
