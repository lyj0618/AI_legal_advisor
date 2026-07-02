import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

conn = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "legal_ai.db")
cur = conn.cursor()
cur.execute("select name, cleaned_location, timeliness_json from documents")
for name, cleaned, raw in cur.fetchall():
    if not raw:
        continue
    t = json.loads(raw)
    if t.get("level") != "ok":
        print("=" * 60)
        print(name)
        print("level:", t.get("level"), "warnings:", t.get("warning_count"))
        for w in t.get("warnings", [])[:3]:
            print(" -", w)
conn.close()
