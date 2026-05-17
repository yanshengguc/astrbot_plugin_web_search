import json
from typing import AsyncIterator

import httpx

from .base import (
    BaseLLMProvider, SYSTEM_PROMPT,
    AUTO_SEARCH_JUDGE_PROMPT, FOLLOWUP_JUDGE_PROMPT,
    format_results, format_citations, fallback_text,
)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API（非 OpenAI 兼容格式）。"""

    ENDPOINT = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    async def summarize(self, query: str, results: list,
                        system_prompt: str = SYSTEM_PROMPT) -> str:
        if not results:
            return "未找到相关搜索结果。"

        results_text = format_results(results)
        user_message = f"用户问题：{query}\n\n搜索结果：\n{results_text}"

        try:
            content = await self._chat(system_prompt, user_message, stream=False)
            return content
        except Exception:
            return fallback_text(results)

    async def summarize_stream(self, query: str, results: list,
                               system_prompt: str = SYSTEM_PROMPT) -> AsyncIterator[str]:
        if not results:
            yield "未找到相关搜索结果。"
            return

        results_text = format_results(results)
        user_message = f"用户问题：{query}\n\n搜索结果：\n{results_text}"

        try:
            async for chunk in self._chat_stream(system_prompt, user_message):
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

    # ── 底层 API 调用 ───────────────────────────────────────

    async def _chat(self, system: str, user: str, stream: bool = False) -> str:
        body = {
            "model": self.model,
            "max_tokens": 1500,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if not stream:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self.ENDPOINT,
                    json=body,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]
        else:
            raise NotImplementedError

    async def _chat_stream(self, system: str, user: str) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "max_tokens": 1500,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", self.ENDPOINT,
                json=body, headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                            if event["type"] == "content_block_delta":
                                text = event["delta"].get("text", "")
                                if text:
                                    yield text
                        except (json.JSONDecodeError, KeyError):
                            pass

    async def optimize_query(self, message: str) -> str:
        prompt = (
            f"将用户消息改写成一个适合搜索引擎的关键词短语（5-15字）。"
            f"只输出改写后的搜索词，不要加任何解释或标点。\n\n"
            f"用户消息：{message}\n\n"
            f"搜索词："
        )
        try:
            content = await self._chat("", prompt)
            optimized = content.strip()
            return optimized if optimized else message
        except Exception:
            return message

    async def _yes_no_judge(self, prompt: str) -> bool:
        try:
            content = await self._chat("", prompt)
            return "YES" in content.strip().upper()
        except Exception:
            return False

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
