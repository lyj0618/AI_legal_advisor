import json
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def _now():
    return datetime.utcnow()


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    kb_type = Column(String(16), default="legal")  # legal | case
    embedding_model = Column(String(120), default="text-embedding-v2")
    chunk_method = Column(String(32), default="naive")
    permission = Column(String(16), default="me")
    language = Column(String(16), default="Chinese")
    similarity_threshold = Column(Float, default=0.2)
    vector_similarity_weight = Column(Float, default=0.3)
    pagerank = Column(Float, default=0.0)
    parser_config = Column(Text, default="{}")
    create_date = Column(DateTime, default=_now)

    documents = relationship("Document", back_populates="dataset", cascade="all, delete-orphan")
    chat_links = relationship("ChatDataset", back_populates="dataset", cascade="all, delete-orphan")

    @property
    def parser_config_dict(self):
        try:
            return json.loads(self.parser_config or "{}")
        except json.JSONDecodeError:
            return {}

    def document_count(self, db):
        return db.query(Document).filter(Document.dataset_id == self.id).count()


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    name = Column(String(500), nullable=False)
    location = Column(String(1000), default="")
    cleaned_location = Column(String(1000), default="")
    clean_run = Column(String(16), default="0")  # 0 待清洗 / RUNNING 清洗中 / 1 已清洗
    clean_progress = Column(Float, default=0.0)
    timeliness_json = Column(Text, default="")
    status = Column(String(4), default="1")
    chunk_method = Column(String(32), default="naive")
    chunk_count = Column(Integer, default=0)
    run = Column(String(16), default="0")  # 0 待分块 / RUNNING 分块中 / 1 已完成
    progress = Column(Float, default=0.0)
    process_begin_at = Column(DateTime, nullable=True)
    process_duration = Column(Float, nullable=True)
    create_date = Column(DateTime, default=_now)

    dataset = relationship("Dataset", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    # JSON array of image filenames extracted from docx (e.g. ["img_000.png", ...])
    images = Column(Text, default="[]")
    available = Column(Boolean, default=True)
    important_keywords = Column(Text, default="[]")
    embedding = Column(Text, default="")

    document = relationship("Document", back_populates="chunks")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    expert_role = Column(String(100), default="")
    color = Column(String(16), default="#2563eb")
    top_k = Column(Integer, default=1024)
    prompt_config = Column(Text, default="{}")
    # 专家模板：owner_username 为空；用户会话：owner_username 为当前用户
    owner_username = Column(String(64), nullable=True, index=True)
    template_id = Column(String(36), ForeignKey("chats.id"), nullable=True, index=True)
    is_published = Column(Boolean, default=False)
    builtin_expert_id = Column(String(32), nullable=True, index=True)
    create_date = Column(DateTime, default=_now)

    datasets = relationship("ChatDataset", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")


class ChatDataset(Base):
    __tablename__ = "chat_datasets"

    chat_id = Column(String(36), ForeignKey("chats.id"), primary_key=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), primary_key=True)
    chat = relationship("Chat", back_populates="datasets")
    dataset = relationship("Dataset", back_populates="chat_links")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(16), default="consultant")  # admin | consultant
    is_active = Column(Boolean, default=True)
    create_date = Column(DateTime, default=_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(36), ForeignKey("chats.id"), nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    attachments_json = Column(Text, default="[]")
    # JSON array of document image URLs referenced in this message (for assistant role)
    images = Column(Text, default="[]")
    feedback = Column(String(16), nullable=True)  # like | dislike
    create_date = Column(DateTime, default=_now)

    chat = relationship("Chat", back_populates="messages")


class QaRecord(Base):
    """问答对缓存：高置信度命中时直接返回答案。"""

    __tablename__ = "qa_records"

    id = Column(String(36), primary_key=True)
    template_id = Column(String(36), nullable=True, index=True)
    chat_id = Column(String(36), nullable=True)
    assistant_message_id = Column(Integer, nullable=True, unique=True, index=True)
    question = Column(Text, nullable=False)
    question_norm = Column(String(500), default="", index=True)
    answer = Column(Text, nullable=False)
    confidence = Column(String(16), default="low")  # high | low
    feedback = Column(String(16), nullable=True)  # like | dislike
    question_embedding = Column(Text, default="")
    doc_images = Column(Text, default="[]")  # JSON array of doc image URLs carried by the answer
    hit_count = Column(Integer, default=0)
    create_date = Column(DateTime, default=_now)
    update_date = Column(DateTime, default=_now, onupdate=_now)
