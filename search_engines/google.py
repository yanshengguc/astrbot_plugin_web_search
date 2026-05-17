import httpx
from .base import BaseSearchEngine, SearchResult, SearchResponse


class GoogleEngine(BaseSearchEngine):
    """Google Custom Search JSON API。需要 API Key + CSE ID。"""

    ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cse_id: str):
        self.api_key = api_key
        self.cse_id = cse_id

    async def search(self, query: str, max_results: int = 5) -> SearchResponse:
        response = SearchResponse(query=query, engine="Google")
        if not self.api_key or not self.cse_id:
            response.error = "Google API Key 或 CSE ID 未配置"
            return response

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.ENDPOINT,
                    params={
                        "key": self.api_key,
                        "cx": self.cse_id,
                        "q": query,
                        "num": min(max_results, 10),
                        "lr": "lang_zh-CN"
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            for item in data.get("items", [])[:max_results]:
                response.results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", "")
                ))
        except Exception as e:
            response.error = str(e)
        return response
