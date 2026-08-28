from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashscope_api_key: str = ""
    chat_model: str = "qwen-turbo"
    vision_model: str = "qwen-vl-plus"
    embedding_model: str = "text-embedding-v3"
    host: str = "127.0.0.1"
    port: int = 8002
    data_dir: str = "./data"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    max_upload_mb: int = 50
    max_chat_image_mb: int = 5
    max_chat_images: int = 3
    allowed_upload_extensions: str = ".txt,.md,.pdf,.csv,.docx"
    use_vector_index: bool = True

    # 登录认证（演示环境，生产请修改）
    jwt_secret: str = "please-set-a-random-secret-at-least-32-characters-long"
    jwt_expire_hours: int = 72
    auth_username: str = "admin"
    auth_password: str = "LegalAi@2026"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "uploads").mkdir(exist_ok=True)
        (p / "chat_images").mkdir(exist_ok=True)
        (p / "doc_images").mkdir(exist_ok=True)
        (p / "indexes").mkdir(exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return max(1, self.max_upload_mb) * 1024 * 1024

    @property
    def allowed_upload_ext_set(self) -> set[str]:
        exts = set()
        for raw in self.allowed_upload_extensions.split(","):
            ext = raw.strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            exts.add(ext)
        return exts or {".txt", ".md", ".pdf", ".csv", ".docx"}


settings = Settings()
