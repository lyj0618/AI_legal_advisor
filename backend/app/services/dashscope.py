import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def format_dashscope_error(status_code: int, body: str, *, service: str = "模型") -> str:
    """将 DashScope 原始错误转为用户可读的提示。"""
    code = ""
    message = ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            code = str(data.get("code") or (data.get("error") or {}).get("code") or "")
            message = str(
                data.get("message")
                or (data.get("error") or {}).get("message")
                or data.get("error")
                or ""
            )
    except (json.JSONDecodeError, TypeError):
        message = body[:200]

    if code == "Arrearage":
        return (
            f"{service}服务不可用：阿里云百炼账户欠费或余额不足。"
            "请登录阿里云控制台为 Model Studio 充值后再试。"
        )
    if status_code == 401 or code in ("InvalidApiKey", "invalid_api_key"):
        return f"{service}服务不可用：API Key 无效，请检查 backend/.env 中的 DASHSCOPE_API_KEY。"
    if status_code == 429:
        return f"{service}服务繁忙（请求过于频繁），请稍后再试。"
    if message:
        return f"{service}服务异常（{status_code}）：{message}"
    return f"{service}服务异常（HTTP {status_code}）"


class DashScopeClient:
    def __init__(self):
        self.api_key = settings.dashscope_api_key
        self.chat_model = settings.chat_model
        self.embedding_model = settings.embedding_model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
    ) -> str:
        if not self.api_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY，请在 backend/.env 中设置")

        payload = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{DASHSCOPE_BASE}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                raise RuntimeError(format_dashscope_error(resp.status_code, resp.text, service="对话"))
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY，请在 backend/.env 中设置")

        payload = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{DASHSCOPE_BASE}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise RuntimeError(
                        format_dashscope_error(
                            resp.status_code,
                            body.decode("utf-8", errors="ignore"),
                            service="对话",
                        )
                    )
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        payload = {
            "model": self.embedding_model,
            "input": {"texts": texts},
            "parameters": {"text_type": "document"},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(format_dashscope_error(resp.status_code, resp.text, service="向量嵌入"))
            data = resp.json()
            if "output" in data and "embeddings" in data["output"]:
                return [item["embedding"] for item in data["output"]["embeddings"]]
            if "data" in data:
                return [item["embedding"] for item in data["data"]]
            raise RuntimeError(f"嵌入 API 响应异常: {json.dumps(data, ensure_ascii=False)[:200]}")

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY")
        if not texts:
            return []

        max_chars = 1800
        batch_size = 10
        normalized = [t[:max_chars] if len(t) > max_chars else t for t in texts]
        all_embeddings: list[list[float]] = []
        for i in range(0, len(normalized), batch_size):
            batch = normalized[i : i + batch_size]
            all_embeddings.extend(await self._embed_batch(batch))
        return all_embeddings


dashscope_client = DashScopeClient()
