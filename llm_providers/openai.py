from typing import AsyncIterator

from openai import AsyncOpenAI

from .base import (
    BaseLLMProvider, SYSTEM_PROMPT,
    AUTO_SEARCH_JUDGE_PROMPT, FOLLOWUP_JUDGE_PROMPT,
    format_results, format_citations, fallback_text,
)


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI / DeepSeek / Ollama / 硅基流动 / 豆包 等兼容接口。"""

    def __init__(self, model: str, api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key)
        self.client = AsyncOpenAI(
            base_url=base_url or "https://api.openai.com/v1",
            api_key=api_key if api_key else "sk-placeholder",
        )

    async def summarize(self, query: str, results: list,
                        system_prompt: str = SYSTEM_PROMPT) -> str:
        if not results:
            return "未找到相关搜索结果。"

        results_text = format_results(results)
        user_message = f"用户问题：{query}\n\n搜索结果：\n{results_text}"

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            content = resp.choices[0].message.content or ""
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
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1500,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
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

    async def optimize_query(self, message: str) -> str:
        prompt = (
            f"将用户消息改写成一个适合搜索引擎的关键词短语（5-15字）。"
            f"只输出改写后的搜索词，不要加任何解释或标点。\n\n"
            f"用户消息：{message}\n\n"
            f"搜索词："
        )
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=30,
            )
            optimized = resp.choices[0].message.content.strip()
            return optimized if optimized else message
        except Exception:
            return message

    async def _yes_no_judge(self, prompt: str) -> bool:
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=5,
            )
            reply = resp.choices[0].message.content.strip().upper()
            return "YES" in reply
        except Exception:
            return False
