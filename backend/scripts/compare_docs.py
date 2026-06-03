import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.chunking import split_chunks, _split_legal_articles, _LEGAL_ARTICLE_HEAD

db = Path(__file__).resolve().parents[1] / "data" / "legal_ai.db"
root = Path(__file__).resolve().parents[1]
c = sqlite3.connect(db)
cur = c.cursor()
rows = cur.execute(
    "select id, name, create_date, chunk_count, cleaned_location from documents "
    "where name like '%劳动合同法%(1)%' order by create_date desc"
).fetchall()
lines = []
for doc_id, name, created, chunk_count, cleaned_loc in rows:
    lines.append(f"=== {doc_id} | {created} | chunks={chunk_count} ===")
    p = root / cleaned_loc if cleaned_loc else None
    if p and p.exists():
        t = p.read_text(encoding="utf-8")
        m = list(_LEGAL_ARTICLE_HEAD.finditer(t))
        parts = split_chunks(t)
        lines.append(f"  cleaned: {p.name} len={len(t)} article_heads={len(m)} split_now={len(parts)}")
        lines.append(f"  first80: {t[:80].replace(chr(10),' ')}")
        lines.append(f"  sample around 第二条: ...")
        idx = t.find("第二条")
        if idx >= 0:
            lines.append(f"  [{idx-20}:{idx+40}] {repr(t[max(0,idx-20):idx+40])}")
        chs = cur.execute(
            "select length(content), substr(content,1,60) from chunks where document_id=? order by rowid limit 3",
            (doc_id,),
        ).fetchall()
        for ln, head in chs:
            lines.append(f"  db_chunk len={ln} {head.replace(chr(10),' ')[:60]}")
    else:
        lines.append(f"  NO cleaned file: {cleaned_loc}")

out = Path(__file__).resolve().parent / "compare_docs_out.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out)
