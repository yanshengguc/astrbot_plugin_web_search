from abc import ABC, abstractmethod
from typing import AsyncIterator


# ── 共享 Prompt，不绑定具体 API ─────────────────────────────

SYSTEM_PROMPT = """你是一个在聊天群里帮大家查资料的助手。你说话自然、亲切，像朋友聊天一样。

规则：
1. 用口语化的方式回答，不要像写论文或报告。可以用"我查了一下"、"网上说"这类自然的开头。
2. 基于搜索结果回答，不要编造。如果搜索结果里没有，就老实说"没找到相关的"。
3. 回答尽量简洁，不要堆砌。如果信息很多，分几点说就行。
4. 如果有朋友追问上一轮搜索的细节，结合历史结果继续聊。
5. 绝对不要主动贴网址链接！用户只是想了解信息，不是要访问网站。只有当用户明确说"给我链接"、"网址发一下"、"来源发我"时才附上链接。"""

FOLLOWUP_SYSTEM_PROMPT = """你是一个在聊天群里帮大家查资料的助手。

上次朋友问的是：{previous_query}
当时你查到的信息：
{previous_results}

现在朋友追问了，请基于上面的历史信息自然地回答。说话口语化，像在聊天一样。
绝对不要主动贴网址链接，除非用户明确要求。"""

AUTO_SEARCH_JUDGE_PROMPT = """判断用户的消息是否需要联网搜索才能回答。你只能回复 "YES" 或 "NO"。

需要搜索的情况：
- 询问实时信息（天气、新闻、股价等）
- 询问事实性知识（人物、事件、数据等）
- 要求查找资料或信息
- 询问最新动态

不需要搜索的情况：
- 日常问候、闲聊
- 纯粹的情感表达
- 对机器人本身功能的询问
- 已经有明确答案的主观问题

用户消息：{message}

请只回复 "YES" 或 "NO"。"""

FOLLOWUP_JUDGE_PROMPT = """判断用户的消息是否在追问上一轮搜索结果。你只能回复 "YES" 或 "NO"。

上一轮搜索问题：{previous_query}
用户消息：{message}

追问的特征：
- "详细说下"、"展开讲讲"、"第二点"、"继续说"、"还有吗"
- 与上一轮搜索主题高度相关的问题

请只回复 "YES" 或 "NO"。"""


# ── 格式化工具，所有 Provider 共用 ──────────────────────────

def format_results(results: list) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"### [{i}] {r.title}\n"
            f"- 链接：{r.url}\n"
            f"- 摘要：{r.snippet or '无描述'}"
        )
    return "\n\n".join(parts)


def format_citations(results: list) -> str:
    if not results:
        return ""
    lines = ["\n\n查自："]
    for r in results:
        lines.append(f" · [{r.title}]({r.url})")
    return "".join(lines)


def fallback_text(results: list) -> str:
    parts = ["帮你找到了这些，看看有没有要的：\n"]
    for i, r in enumerate(results, 1):
        parts.append(f"{i}. [{r.title}]({r.url})\n   {r.snippet}\n")
    return "\n".join(parts)


# ── 抽象基类 ───────────────────────────────────────────────

class BaseLLMProvider(ABC):

    def __init__(self, model: str, api_key: str = ""):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    async def summarize(self, query: str, results: list,
                        system_prompt: str = SYSTEM_PROMPT) -> str:
        ...

    @abstractmethod
    async def summarize_stream(self, query: str, results: list,
                               system_prompt: str = SYSTEM_PROMPT) -> AsyncIterator[str]:
        ...

    async def summarize_followup(self, query: str,
                                 prev_results: list, prev_query: str) -> str:
        results_text = format_results(prev_results)
        prompt = FOLLOWUP_SYSTEM_PROMPT.format(
            previous_query=prev_query, previous_results=results_text
        )
        return await self.summarize(query, prev_results, system_prompt=prompt)

    async def summarize_followup_stream(self, query: str,
                                        prev_results: list, prev_query: str
                                        ) -> AsyncIterator[str]:
        results_text = format_results(prev_results)
        prompt = FOLLOWUP_SYSTEM_PROMPT.format(
            previous_query=prev_query, previous_results=results_text
        )
        async for chunk in self.summarize_stream(query, prev_results, system_prompt=prompt):
            yield chunk

    @abstractmethod
    async def should_search(self, message: str) -> bool:
        ...

    @abstractmethod
    async def is_followup(self, message: str, previous_query: str) -> bool:
        ...

    @abstractmethod
    async def optimize_query(self, message: str) -> str:
        """将用户消息优化为搜索引擎关键词，失败时返回原消息。"""
        ...
