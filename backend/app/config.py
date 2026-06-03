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
    embedding_model: str = "text-embedding-v3"
    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: str = "./data"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 登录认证（演示环境，生产请修改）
    jwt_secret: str = "legal-ai-advisor-change-me-in-production"
    jwt_expire_hours: int = 72
    auth_username: str = "admin"
    auth_password: str = "123456"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "uploads").mkdir(exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
