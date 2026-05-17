import asyncio
from .base import BaseSearchEngine, SearchResponse


__all__ = ["SearchRouter"]


def _build_engine(engine_type: str, config: dict) -> BaseSearchEngine | None:
    """返回引擎实例，如果该引擎未配置则返回 None。"""
    if engine_type == "duckduckgo":
        from .duckduckgo import DuckDuckGoEngine
        return DuckDuckGoEngine()
    elif engine_type == "bing":
        if not config.get("bing_api_key"):
            return None
        from .bing import BingEngine
        return BingEngine(config["bing_api_key"])
    elif engine_type == "google":
        if not config.get("google_api_key") or not config.get("google_cse_id"):
            return None
        from .google import GoogleEngine
        return GoogleEngine(config["google_api_key"], config["google_cse_id"])
    else:
        return None


class SearchRouter:
    """搜索引擎路由器：主引擎 + 回退链路。

    未配置 API Key 的引擎在初始化时自动跳过，
    搜索时依次尝试已配置的引擎直到成功。
    """

    def __init__(self, primary: str, config: dict, fallback_chain: list = None):
        if fallback_chain is None:
            fallback_chain = ["duckduckgo", "bing", "google"]

        # 构建回退链：主引擎优先，跳过未配置的
        ordered = [primary] + [e for e in fallback_chain if e != primary]
        self.engines: list[tuple[str, BaseSearchEngine]] = []
        self.skipped: list[str] = []

        for name in ordered:
            engine = _build_engine(name, config)
            if engine is not None:
                self.engines.append((name, engine))
            else:
                self.skipped.append(name)

    async def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """依次尝试各引擎，直到成功。"""
        if not self.engines:
            return SearchResponse(
                query=query, engine="none",
                error="没有可用的搜索引擎（DuckDuckGo 免费可直接用，Bing/Google 需在 config.yaml 配置 API Key）"
            )

        errors = []
        for name, engine in self.engines:
            try:
                resp = await asyncio.wait_for(
                    engine.search(query, max_results=max_results),
                    timeout=15,
                )
                if resp.results:
                    resp.engine = name
                    return resp
                if resp.error:
                    errors.append(f"[{name}] {resp.error}")
            except asyncio.TimeoutError:
                errors.append(f"[{name}] 超时")
            except Exception as e:
                errors.append(f"[{name}] {e}")

        err_detail = "; ".join(errors)
        skipped_hint = f" (已跳过: {', '.join(self.skipped)})" if self.skipped else ""
        return SearchResponse(
            query=query,
            engine="all",
            error=f"搜索失败: {err_detail}{skipped_hint}",
        )
