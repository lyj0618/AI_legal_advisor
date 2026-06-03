import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.chunking import split_chunks

db = Path(__file__).resolve().parents[1] / "data" / "legal_ai.db"
out = Path(__file__).resolve().parent / "inspect_chunks_out.txt"
c = sqlite3.connect(db)
cur = c.cursor()
lines = []
ds = "3d0915df-d8ff-4946-a065-e2dafcfd82f7"
for row in cur.execute(
    "select id, name, chunk_count, clean_run, run, cleaned_location from documents where dataset_id=?",
    (ds,),
):
    lines.append(f"{row[0]} {row[1]} chunks={row[2]} clean={row[3]} run={row[4]}")
    doc_id, cleaned_loc = row[0], row[5]
    n = cur.execute("select count(*) from chunks where document_id=?", (doc_id,)).fetchone()[0]
    lines.append(f"  db chunk rows={n}")
    for ch in cur.execute(
        "select length(content), content from chunks where document_id=? order by rowid limit 5",
        (doc_id,),
    ):
        lines.append(f"  len={ch[0]} head={ch[1][:80].replace(chr(10), ' ')}")
    if cleaned_loc:
        p = Path(__file__).resolve().parents[1] / cleaned_loc
        if p.exists():
            t = p.read_text(encoding="utf-8")
            parts = split_chunks(t)
            lines.append(f"  split_chunks now => {len(parts)} parts, first starts: {parts[0][:40]!r}")
out.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out)
