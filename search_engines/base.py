from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    engine: str = ""
    error: str = ""


class BaseSearchEngine(ABC):

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> SearchResponse:
        ...
