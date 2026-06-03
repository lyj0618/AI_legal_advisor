from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    f"sqlite:///{settings.data_path / 'legal_ai.db'}",
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_chats_columns():
    """为已有 SQLite 库补充新字段。"""
    import sqlite3

    db_path = settings.data_path / "legal_ai.db"
    if not db_path.exists():
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(chats)")
    cols = {row[1] for row in cur.fetchall()}
    alters = []
    if "owner_username" not in cols:
        alters.append("ALTER TABLE chats ADD COLUMN owner_username VARCHAR(64)")
    if "template_id" not in cols:
        alters.append("ALTER TABLE chats ADD COLUMN template_id VARCHAR(36)")
    if "is_published" not in cols:
        alters.append("ALTER TABLE chats ADD COLUMN is_published BOOLEAN DEFAULT 0")
    if "builtin_expert_id" not in cols:
        alters.append("ALTER TABLE chats ADD COLUMN builtin_expert_id VARCHAR(32)")
    if "color" not in cols:
        alters.append("ALTER TABLE chats ADD COLUMN color VARCHAR(16) DEFAULT '#2563eb'")
    cur.execute("PRAGMA table_info(documents)")
    doc_cols = {row[1] for row in cur.fetchall()}
    if "cleaned_location" not in doc_cols:
        alters.append("ALTER TABLE documents ADD COLUMN cleaned_location VARCHAR(1000) DEFAULT ''")
    if "clean_run" not in doc_cols:
        alters.append("ALTER TABLE documents ADD COLUMN clean_run VARCHAR(16) DEFAULT '0'")
    if "clean_progress" not in doc_cols:
        alters.append("ALTER TABLE documents ADD COLUMN clean_progress FLOAT DEFAULT 0")
    for sql in alters:
        cur.execute(sql)
    if alters:
        cur.execute(
            "UPDATE chats SET is_published = 1 WHERE owner_username IS NULL AND template_id IS NULL"
        )
        cur.execute(
            "UPDATE documents SET clean_run = '1', clean_progress = 1.0 "
            "WHERE cleaned_location IS NOT NULL AND cleaned_location != ''"
        )
        cur.execute(
            "UPDATE documents SET run = '1', progress = 1.0 WHERE chunk_count > 0"
        )
    conn.commit()
    conn.close()


def init_db():
    from app import models  # noqa: F401
    from app.services.expert_seed import ensure_builtin_expert_templates
    from app.services.user_bootstrap import ensure_default_admin

    Base.metadata.create_all(bind=engine)
    _migrate_chats_columns()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        ensure_builtin_expert_templates(db)
    finally:
        db.close()
