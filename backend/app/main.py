from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, chats, datasets, doc_images, experts, qa_records, retrieval, stats, users, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI 智能知识助手 API",
    description="基于 qwen-turbo 的多行业知识问答后端",
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
app.include_router(doc_images.router)
app.include_router(chats.router)
app.include_router(retrieval.router)
app.include_router(experts.router)
app.include_router(users.router)
app.include_router(stats.router)
app.include_router(qa_records.router)
app.include_router(ws.router)


from app.services.chunking import CHUNKING_VERSION


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": settings.chat_model,
        "vision_model": settings.vision_model,
        "embedding_model": settings.embedding_model,
        "dashscope_configured": bool(settings.dashscope_api_key.strip()),
        "chunking_version": CHUNKING_VERSION,
        "vector_index": settings.use_vector_index,
        "async_doc_tasks": True,
    }
