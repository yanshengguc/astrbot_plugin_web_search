import httpx
from .base import BaseSearchEngine, SearchResult, SearchResponse


class BingEngine(BaseSearchEngine):
    """Bing Web Search API v7。需要 Azure API Key。"""

    ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> SearchResponse:
        response = SearchResponse(query=query, engine="Bing")
        if not self.api_key:
            response.error = "Bing API Key 未配置"
            return response

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.ENDPOINT,
                    params={"q": query, "count": max_results, "mkt": "zh-CN"},
                    headers={
                        "Ocp-Apim-Subscription-Key": self.api_key,
                        "User-Agent": "astrbot-web-search/1.0.0"
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            for item in data.get("webPages", {}).get("value", [])[:max_results]:
                response.results.append(SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", "")
                ))
        except Exception as e:
            response.error = str(e)
        return response
