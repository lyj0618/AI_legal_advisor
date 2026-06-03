import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "legal_ai.db"
c = sqlite3.connect(db)
for r in c.execute(
    "select id, name, chunk_count, cleaned_location from documents "
    "where chunk_count > 0 and chunk_count < 50"
):
    print(r)
