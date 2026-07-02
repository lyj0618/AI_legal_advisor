"""对指定文档重新分块"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8002"
DATASET = "3d0915df-d8ff-4946-a065-e2dafcfd82f7"
DOC = "1f7e628e-2fe1-4c3d-94a0-813d6abf14a7"


def request(method, path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    login = request("POST", "/api/v1/auth/login", {"username": "admin", "password": "LegalAi@2026"})
    token = login["data"]["access_token"]
    body = request(
        "PUT",
        f"/api/v1/datasets/{DATASET}/documents/{DOC}",
        {"run": "1"},
        token=token,
    )
    chunk_count = (body.get("data") or {}).get("chunk_count")
    print(json.dumps({"code": body.get("code"), "message": body.get("message"), "chunk_count": chunk_count}, ensure_ascii=False))
    return 0 if body.get("code") == 0 and chunk_count and chunk_count > 50 else 1


if __name__ == "__main__":
    sys.exit(main())
