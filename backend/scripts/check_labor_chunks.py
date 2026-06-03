import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.chunking import split_chunks

root = Path(__file__).resolve().parents[1]
db = root / "data" / "legal_ai.db"
c = sqlite3.connect(db)
rows = c.execute(
    "select id, name, chunk_count, cleaned_location, create_date from documents "
    "order by create_date desc limit 15"
).fetchall()
lines = []
for doc_id, name, cc, loc, created in rows:
    p = root / loc.replace("\\", "/")
    t = p.read_text(encoding="utf-8") if p.exists() else ""
    parts = split_chunks(t)
    ch0 = c.execute(
        "select length(content) from chunks where document_id=? order by rowid limit 1",
        (doc_id,),
    ).fetchone()
    has_toc = "目录" in t[:2000] or "目\n\n录" in t[:2000]
    lines.append(
        f"{created} {name[:40]} db={cc} len0={ch0[0] if ch0 else 0} now={len(parts)} toc={has_toc}"
    )
(Path(__file__).parent / "check_labor_out.txt").write_text("\n".join(lines), encoding="utf-8")
