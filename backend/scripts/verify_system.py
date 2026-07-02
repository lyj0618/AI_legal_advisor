"""系统功能全面验证（不输出敏感信息）。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.services.dashscope import dashscope_client  # noqa: E402

BASE = "http://127.0.0.1:8002"
SAMPLE = Path(__file__).resolve().parents[2] / "sample-docs" / "劳动合同法节选.txt"


def record(results: list, name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


async def check_dashscope(results: list):
    key = settings.dashscope_api_key or ""
    record(
        results,
        "DashScope Key 已配置",
        bool(key) and key != "sk-your-dashscope-api-key-here",
        f"长度 {len(key)}，前缀 sk-={'是' if key.startswith('sk-') else '否'}",
    )
    if key != key.strip():
        record(results, "DashScope Key 无首尾空格", False, "检测到首尾空白，请修正 .env")
    else:
        record(results, "DashScope Key 无首尾空格", True)

    try:
        em = await dashscope_client.embed_texts(["测试嵌入"])
        record(results, "向量嵌入 API", bool(em and em[0]), f"维度 {len(em[0]) if em and em[0] else 0}")
    except Exception as e:
        record(results, "向量嵌入 API", False, str(e)[:120])

    try:
        ans = await dashscope_client.chat_completion([{"role": "user", "content": "说一个字：好"}])
        record(results, "对话 API", len(ans) > 0, f"回答长度 {len(ans)}")
    except Exception as e:
        record(results, "对话 API", False, str(e)[:120])


def run_http_flow(results: list):
    c = httpx.Client(timeout=180.0, base_url=BASE)
    token = None

    r = c.get("/health")
    h = r.json() if r.status_code == 200 else {}
    record(
        results,
        "健康检查",
        r.status_code == 200 and h.get("status") == "ok",
        str(h),
    )

    for pwd in ("LegalAi@2026", "123456"):
        r = c.post("/api/v1/auth/login", json={"username": "admin", "password": pwd})
        body = r.json()
        if body.get("code") == 0 and body.get("data", {}).get("access_token"):
            token = body["data"]["access_token"]
            record(results, "管理员登录", True, f"使用密码 {pwd}")
            break
    if not token:
        record(results, "管理员登录", False, "两种默认密码均失败")
        return

    auth = {"Authorization": f"Bearer {token}"}

    r = c.get("/api/v1/auth/me", headers=auth)
    record(results, "获取当前用户", r.json().get("code") == 0)

    r = c.get("/api/v1/experts", headers=auth)
    experts = r.json().get("data") or []
    record(results, "专家列表（已绑知识库）", r.json().get("code") == 0, f"共 {len(experts)} 项")

    r = c.get("/api/v1/datasets", headers=auth)
    datasets = r.json().get("data") or []
    record(results, "知识库列表", r.json().get("code") == 0, f"共 {len(datasets)} 个")

    # 上传限制
    r = c.post("/api/v1/datasets", headers=auth, json={"name": "VERIFY_UPLOAD", "description": "tmp"})
    dsid = (r.json().get("data") or {}).get("id")
    if dsid:
        r = c.post(
            f"/api/v1/datasets/{dsid}/documents",
            headers=auth,
            files={"file": ("virus.exe", b"x", "application/octet-stream")},
        )
        record(
            results,
            "上传类型校验",
            r.json().get("code") != 0 and "不支持" in (r.json().get("message") or ""),
            r.json().get("message", ""),
        )

    doc_id = None
    if dsid and SAMPLE.exists():
        with SAMPLE.open("rb") as f:
            r = c.post(
                f"/api/v1/datasets/{dsid}/documents",
                headers=auth,
                files={"file": (SAMPLE.name, f, "text/plain")},
            )
        body = r.json()
        doc_id = (body.get("data") or {}).get("id")
        record(results, "上传合法文档", body.get("code") == 0 and bool(doc_id))

    if dsid and doc_id:
        r = c.put(
            f"/api/v1/datasets/{dsid}/documents/{doc_id}",
            headers=auth,
            json={"clean": "1"},
        )
        body = r.json()
        record(
            results,
            "文档清洗",
            body.get("code") == 0 and body.get("data", {}).get("clean_run") == "1",
            body.get("message", ""),
        )

        r = c.put(
            f"/api/v1/datasets/{dsid}/documents/{doc_id}",
            headers=auth,
            json={"run": "1"},
        )
        body = r.json()
        chunk_count = (body.get("data") or {}).get("chunk_count", 0)
        msg = body.get("message", "")
        embed_ok = "嵌入失败" not in msg
        record(results, "文档分块", body.get("code") == 0 and chunk_count > 0, f"切片 {chunk_count} 条")
        record(results, "分块向量嵌入", embed_ok, msg[:100] if msg else "无消息")

        r = c.get(f"/api/v1/datasets/{dsid}/documents/{doc_id}", headers=auth)
        record(
            results,
            "文档下载（带 Token）",
            r.status_code == 200 and len(r.content) > 0,
            f"HTTP {r.status_code}, {len(r.content)} bytes",
        )

        r = c.get(f"/api/v1/datasets/{dsid}/documents/{doc_id}")
        record(results, "文档下载（无 Token）", r.status_code == 401, f"HTTP {r.status_code}")

        r = c.post(
            "/api/v1/retrieval",
            headers=auth,
            json={"dataset_ids": [dsid], "question": "试用期最长多久？", "top_k": 3},
        )
        if r.status_code == 200:
            hits = (r.json().get("data") or {}).get("chunks") or []
            record(results, "知识库检索", r.json().get("code") == 0 and len(hits) > 0, f"命中 {len(hits)} 条")
        else:
            record(results, "知识库检索", False, f"HTTP {r.status_code}（多为嵌入 API 失败）")

        r = c.post(
            "/api/v1/chats",
            headers=auth,
            json={"name": "VERIFY_CHAT", "description": "tmp", "kb_ids": [dsid]},
        )
        chat_id = (r.json().get("data") or {}).get("id")
        if chat_id:
            r = c.post(
                f"/api/v1/chats/{chat_id}/completions",
                headers=auth,
                json={"question": "劳动合同试用期有什么规定？请简要回答。", "stream": False},
            )
            body = r.json()
            answer = (body.get("data") or {}).get("answer", "")
            record(
                results,
                "非流式对话",
                body.get("code") == 0 and len(answer) > 10,
                f"回答长度 {len(answer)}",
            )

        c.delete(f"/api/v1/datasets", headers=auth, json={"ids": [dsid]})

    r = c.get("/api/v1/chats")
    record(results, "未登录访问拦截", r.status_code == 401, f"HTTP {r.status_code}")


def main():
    results: list[tuple[str, bool, str]] = []
    print(f"验证目标: {BASE}\n")
    asyncio.run(check_dashscope(results))
    print()
    run_http_flow(results)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n=== 汇总: {passed}/{total} 通过 ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
