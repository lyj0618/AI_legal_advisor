from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, chats, datasets, experts, retrieval, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI 法律顾问助手 API",
    description="基于 qwen-turbo 的法律顾问助手后端",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(datasets.router)
app.include_router(chats.router)
app.include_router(retrieval.router)
app.include_router(experts.router)
app.include_router(users.router)


from app.services.chunking import CHUNKING_VERSION


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "dashscope_configured": bool(settings.dashscope_api_key.strip()),
        "chunking_version": CHUNKING_VERSION,
    }
