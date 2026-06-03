import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "legal_ai.db"
for r in sqlite3.connect(db).execute(
    "select id, name, chunk_count, location from documents"
):
    if "pdf" in (r[1] or "").lower() or "pdf" in (r[3] or "").lower():
        print(r)
