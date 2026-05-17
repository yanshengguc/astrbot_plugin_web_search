import json
from typing import AsyncIterator

import httpx

from .base import (
    BaseLLMProvider, SYSTEM_PROMPT,
    AUTO_SEARCH_JUDGE_PROMPT, FOLLOWUP_JUDGE_PROMPT,
    format_results, format_citations, fallback_text,
)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API（非 OpenAI 兼容格式）。"""

    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, model: str = "gemini-2.0-flash", api_key: str = ""):
        super().__init__(model, api_key)

    # ── 公开接口 ────────────────────────────────────────────

    async def summarize(self, query: str, results: list,
                        system_prompt: str = SYSTEM_PROMPT) -> str:
        if not results:
            return "未找到相关搜索结果。"

        results_text = format_results(results)
        user = f"用户问题：{query}\n\n搜索结果：\n{results_text}"

        try:
            content = await self._generate(system_prompt, user, stream=False)
            return content
        except Exception:
            return fallback_text(results)

    async def summarize_stream(self, query: str, results: list,
                               system_prompt: str = SYSTEM_PROMPT) -> AsyncIterator[str]:
        if not results:
            yield "未找到相关搜索结果。"
            return

        results_text = format_results(results)
        user = f"用户问题：{query}\n\n搜索结果：\n{results_text}"

        try:
            async for chunk in self._generate_stream(system_prompt, user):
                yield chunk
        except Exception:
            yield fallback_text(results)

    async def should_search(self, message: str) -> bool:
        prompt = AUTO_SEARCH_JUDGE_PROMPT.format(message=message)
        return await self._yes_no_judge(prompt)

    async def is_followup(self, message: str, previous_query: str) -> bool:
        prompt = FOLLOWUP_JUDGE_PROMPT.format(
            previous_query=previous_query, message=message
        )
        return await self._yes_no_judge(prompt)

    # ── 底层 API ────────────────────────────────────────────

    def _url(self, endpoint: str) -> str:
        return f"{self.BASE}/models/{self.model}:{endpoint}?key={self.api_key}"

    def _build_payload(self, system: str, user: str) -> dict:
        parts = []
        if system:
            parts.append({"text": system})
        parts.append({"text": user})
        return {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1500,
            },
        }

    async def _generate(self, system: str, user: str, stream: bool = False) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self._url("generateContent"),
                json=self._build_payload(system, user),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _generate_stream(self, system: str, user: str) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", self._url("streamGenerateContent"),
                json=self._build_payload(system, user),
                headers={"Content-Type": "application/json"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if not data_str or data_str == "[DONE]":
                            continue
                        try:
                            event = json.loads(data_str)
                            parts = (event.get("candidates", [{}])[0]
                                     .get("content", {})
                                     .get("parts", []))
                            for p in parts:
                                if "text" in p:
                                    yield p["text"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

    async def optimize_query(self, message: str) -> str:
        prompt = (
            f"将用户消息改写成一个适合搜索引擎的关键词短语（5-15字）。"
            f"只输出改写后的搜索词，不要加任何解释或标点。\n\n"
            f"用户消息：{message}\n\n"
            f"搜索词："
        )
        try:
            content = await self._generate("", prompt)
            optimized = content.strip()
            return optimized if optimized else message
        except Exception:
            return message

    async def _yes_no_judge(self, prompt: str) -> bool:
        try:
            content = await self._generate("", prompt)
            return "YES" in content.strip().upper()
        except Exception:
            return False
