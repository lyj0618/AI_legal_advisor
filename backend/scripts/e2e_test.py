"""端到端 API 流程测试。

用法:
  python scripts/e2e_test.py                    # 测运行中的服务 (默认 8000)
  python scripts/e2e_test.py --inprocess        # 进程内启动应用（推荐，使用最新代码与 .env）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_TXT = ROOT / "sample-docs" / "劳动合同法节选.txt"


class FlowTest:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.client = httpx.Client(timeout=180.0)
        self.token: str | None = None
        self.results: list[tuple[str, bool, str]] = []

    def record(self, name: str, ok: bool, detail: str = ""):
        self.results.append((name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    def api(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = f"{self.base}{path}"
        return self.client.request(method, url, headers=headers, **kwargs)

    def json_body(self, resp: httpx.Response) -> dict:
        try:
            return resp.json()
        except Exception:
            return {"_raw": resp.text[:300]}

    def run(self) -> int:
        # 1. 健康检查
        r = self.client.get(f"{self.base}/health")
        h = self.json_body(r)
        configured = h.get("dashscope_configured", False)
        self.record(
            "健康检查 /health",
            r.status_code == 200 and h.get("status") == "ok",
            json.dumps(h, ensure_ascii=False),
        )
        if not configured:
            self.record("DashScope Key 已配置", False, "dashscope_configured=false，后续 AI 步骤将跳过")
        else:
            self.record("DashScope Key 已配置", True)

        # 2. 登录
        r = self.api("POST", "/api/v1/auth/login", json={"username": "admin", "password": "123456"})
        body = self.json_body(r)
        ok_login = body.get("code") == 0 and body.get("data", {}).get("access_token")
        if ok_login:
            self.token = body["data"]["access_token"]
        self.record("登录 admin/123456", bool(ok_login), body.get("message", ""))

        # 3. /me
        r = self.api("GET", "/api/v1/auth/me")
        body = self.json_body(r)
        self.record("获取当前用户 /auth/me", body.get("code") == 0, body.get("message", ""))

        # 4. 专家列表
        r = self.api("GET", "/api/v1/experts")
        body = self.json_body(r)
        experts = body.get("data") or []
        self.record("专家列表 /experts", body.get("code") == 0 and len(experts) >= 8, f"共 {len(experts)} 项")

        dataset_id = doc_id = chat_id = None

        # 5. 创建知识库
        r = self.api(
            "POST",
            "/api/v1/datasets",
            json={"name": "E2E测试库", "description": "自动化测试"},
        )
        body = self.json_body(r)
        if body.get("code") == 0:
            dataset_id = body["data"]["id"]
        self.record("创建知识库", bool(dataset_id), body.get("message", ""))

        if dataset_id and SAMPLE_TXT.exists():
            with SAMPLE_TXT.open("rb") as f:
                r = self.api(
                    "POST",
                    f"/api/v1/datasets/{dataset_id}/documents",
                    files={"file": (SAMPLE_TXT.name, f, "text/plain")},
                )
            body = self.json_body(r)
            if body.get("code") == 0:
                doc_id = body["data"]["id"]
            self.record("上传示例文档", bool(doc_id), body.get("message", ""))

            if doc_id and configured:
                r = self.api(
                    "PUT",
                    f"/api/v1/datasets/{dataset_id}/documents/{doc_id}",
                    json={"clean": "1"},
                )
                body = self.json_body(r)
                self.record(
                    "清洗文档",
                    body.get("code") == 0 and body.get("data", {}).get("clean_run") == "1",
                    body.get("message", ""),
                )
                r = self.api(
                    "PUT",
                    f"/api/v1/datasets/{dataset_id}/documents/{doc_id}",
                    json={"run": "1"},
                )
                body = self.json_body(r)
                chunk_count = body.get("data", {}).get("chunk_count", 0) if body.get("code") == 0 else 0
                self.record(
                    "分块并嵌入",
                    body.get("code") == 0 and chunk_count > 0,
                    f"chunks={chunk_count}, {body.get('message', '')}",
                )

                r = self.api("GET", f"/api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks")
                body = self.json_body(r)
                n_chunks = len((body.get("data") or {}).get("chunks") or [])
                self.record("查询切片列表", body.get("code") == 0 and n_chunks > 0, f"{n_chunks} 条")

                r = self.api(
                    "POST",
                    "/api/v1/retrieval",
                    json={
                        "dataset_ids": [dataset_id],
                        "question": "试用期最长多久？",
                        "top_k": 3,
                    },
                )
                body = self.json_body(r)
                hits = (body.get("data") or {}).get("chunks") or []
                self.record("知识库检索", body.get("code") == 0 and len(hits) > 0, f"命中 {len(hits)} 条")
            elif doc_id and not configured:
                self.record("解析/检索（需 API Key）", False, "已跳过")
        elif not SAMPLE_TXT.exists():
            self.record("上传示例文档", False, f"缺少文件 {SAMPLE_TXT}")

        # 6. 创建聊天并对话
        if dataset_id and configured:
            r = self.api(
                "POST",
                "/api/v1/chats",
                json={
                    "name": "E2E法律顾问",
                    "description": "测试助手",
                    "kb_ids": [dataset_id],
                },
            )
            body = self.json_body(r)
            if body.get("code") == 0:
                chat_id = body["data"]["id"]
            self.record("创建聊天助手", bool(chat_id), body.get("message", ""))

            if chat_id:
                r = self.api(
                    "POST",
                    f"/api/v1/chats/{chat_id}/completions",
                    json={"question": "劳动合同试用期有什么规定？请简要回答。", "stream": False},
                )
                body = self.json_body(r)
                answer = (body.get("data") or {}).get("answer", "") if body.get("code") == 0 else ""
                self.record(
                    "非流式对话",
                    body.get("code") == 0 and len(answer) > 10,
                    f"回答长度 {len(answer)}",
                )

                stream_ok = False
                deltas: list[str] = []
                stream_ctx = self.client.stream(
                    "POST",
                    f"{self.base}/api/v1/chats/{chat_id}/completions",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"question": "说一个字：好", "stream": True},
                )
                with stream_ctx as stream:
                    for line in stream.iter_lines():
                        if isinstance(line, bytes):
                            line = line.decode("utf-8", errors="ignore")
                        if line.startswith("data: "):
                            try:
                                ev = json.loads(line[6:])
                                if ev.get("type") == "delta":
                                    deltas.append(ev.get("content", ""))
                            except json.JSONDecodeError:
                                pass
                    stream_ok = len("".join(deltas)) > 0
                self.record("流式对话 SSE", stream_ok, f"收到 {len(deltas)} 个 delta")

                r = self.api("GET", f"/api/v1/chats/{chat_id}/messages")
                body = self.json_body(r)
                msgs = body.get("data") or []
                self.record("消息历史", body.get("code") == 0 and len(msgs) >= 2, f"{len(msgs)} 条消息")
        elif not configured:
            self.record("对话流程（需 API Key）", False, "已跳过")

        # 7. 未授权访问应 401
        old = self.token
        self.token = None
        r = self.api("GET", "/api/v1/chats")
        self.record("未登录访问受保护接口返回 401", r.status_code == 401)
        self.token = old

        passed = sum(1 for _, ok, _ in self.results if ok)
        total = len(self.results)
        print(f"\n=== 汇总: {passed}/{total} 通过 ===")
        return 0 if passed == total else 1


class InProcessClient:
    """适配 TestClient，接口与 httpx 调用方式一致。"""

    def __init__(self, test_client, base: str = "http://test"):
        self._tc = test_client
        self.base = base

    def request(self, method: str, url: str, **kwargs):
        path = url.replace(self.base, "") if url.startswith("http") else url
        headers = kwargs.pop("headers", None) or {}
        json_data = kwargs.pop("json", None)
        files = kwargs.pop("files", None)
        content = kwargs.pop("content", None)
        if files:
            # TestClient: files + 无 json
            return self._tc.request(method, path, headers=headers, files=files, data=kwargs.get("data"))
        return self._tc.request(
            method, path, headers=headers, json=json_data, content=content, params=kwargs.get("params")
        )

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def stream(self, method: str, url: str, **kwargs):
        path = url.replace(self.base, "") if url.startswith("http") else url
        headers = kwargs.pop("headers", None) or {}
        json_data = kwargs.pop("json", None)
        return self._tc.stream(method, path, headers=headers, json=json_data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--inprocess", action="store_true", help="在进程内加载 FastAPI 应用（使用 backend/.env）")
    args = p.parse_args()

    if args.inprocess:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from starlette.testclient import TestClient
        from app.main import app

        tc = TestClient(app)
        t = FlowTest("http://test")
        t.client = InProcessClient(tc, "http://test")
        print("模式: 进程内 TestClient（最新代码 + .env）\n")
    else:
        t = FlowTest(args.base)
        print(f"模式: HTTP 远程 {args.base}\n")

    sys.exit(t.run())


if __name__ == "__main__":
    main()
