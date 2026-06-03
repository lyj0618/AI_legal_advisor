import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
db = root / "data" / "legal_ai.db"
c = sqlite3.connect(db)
rows = c.execute(
    "select d.id, d.name, d.chunk_count, "
    "(select max(length(content)) from chunks where document_id=d.id), "
    "(select count(*) from chunks where document_id=d.id) "
    "from documents d order by d.create_date desc"
).fetchall()
lines = ["id | name | chunk_count | max_len | rows"]
for r in rows:
    lines.append(f"{r[0][:8]} | {r[1][:35]} | {r[2]} | {r[3]} | {r[4]}")
(Path(__file__).parent / "check_all_out.txt").write_text("\n".join(lines), encoding="utf-8")
