from .base import BaseSearchEngine, SearchResult, SearchResponse


class DuckDuckGoEngine(BaseSearchEngine):
    """DuckDuckGo 搜索，免费无需 API Key。优先使用 ddgs 库，回退到 HTML 抓取。"""

    async def search(self, query: str, max_results: int = 5) -> SearchResponse:
        response = SearchResponse(query=query, engine="DuckDuckGo")
        try:
            results = await self._search_via_library(query, max_results)
            if results:
                response.results = results
                return response
        except Exception:
            pass

        try:
            results = await self._search_via_lite(query, max_results)
            response.results = results
        except Exception as e:
            response.error = str(e)
        return response

    async def _search_via_library(self, query: str, max_results: int) -> list[SearchResult]:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _sync_search():
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            return list(DDGS().text(query, max_results=max_results, region="cn-zh"))

        with ThreadPoolExecutor(max_workers=1) as executor:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(executor, _sync_search)

        results = []
        for item in raw:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", "")
            ))
        return results

    async def _search_via_lite(self, query: str, max_results: int) -> list[SearchResult]:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    )
                },
                follow_redirects=True,
            )
            resp.raise_for_status()

        return self._parse_lite(resp.text, max_results)

    def _parse_lite(self, html: str, max_results: int) -> list[SearchResult]:
        """解析 DuckDuckGo Lite 的 HTML。"""
        import re

        results = []
        # 使用正则提取：<a href="url">title</a> 后面的文本作为 snippet
        # DuckDuckGo Lite 的结构较简单，正则足够
        rows = re.split(r'<tr[^>]*>', html)

        for row in rows:
            if len(results) >= max_results:
                break

            links = re.findall(
                r'<a\s+[^>]*href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>',
                row, re.DOTALL | re.IGNORECASE
            )

            if not links:
                # backup: any a tag with external href
                links = re.findall(
                    r'<a\s+[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                    row, re.DOTALL
                )
                links = [(u, t) for u, t in links
                         if "duckduckgo.com" not in u and "127.0.0.1" not in u]

            if not links:
                continue

            url, title_raw = links[0]
            title = re.sub(r'<[^>]+>', '', title_raw).strip()

            # 提取 snippet: td 中的文本，排除 a 标签内容
            snippet_match = re.search(
                r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
                row, re.DOTALL
            )
            snippet = ""
            if snippet_match:
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()

            if title and url:
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet[:500]
                ))

        return results
