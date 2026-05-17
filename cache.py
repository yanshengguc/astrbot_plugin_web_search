import time
import hashlib
from collections import defaultdict


class SearchCache:
    """搜索结果缓存，TTL 过期自动失效。"""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._store: dict[str, tuple[float, list]] = {}

    def _key(self, query: str) -> str:
        return hashlib.md5(query.strip().lower().encode()).hexdigest()

    def get(self, query: str) -> list | None:
        key = self._key(query)
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, results = entry
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return results

    def set(self, query: str, results: list):
        self._store[self._key(query)] = (time.time(), results)


class RateLimiter:
    """滑动窗口频率限制。"""

    def __init__(self, max_requests: int = 5, window: float = 60.0):
        self.max_requests = max_requests
        self.window = window
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> bool:
        """检查是否允许请求。返回 True 表示放行。"""
        now = time.time()
        bucket = self._buckets[user_id]

        # 清理过期记录
        cutoff = now - self.window
        self._buckets[user_id] = [t for t in bucket if t > cutoff]

        if len(self._buckets[user_id]) >= self.max_requests:
            return False

        self._buckets[user_id].append(now)
        return True


class ConversationStore:
    """多轮对话上下文存储（按会话 ID）。"""

    def __init__(self, ttl: int = 600):
        self.ttl = ttl
        self._store: dict[str, tuple[float, list, str]] = {}

    def save(self, session_id: str, query: str, results: list):
        """保存最近一次搜索结果。"""
        self._store[session_id] = (time.time(), results, query)

    def get(self, session_id: str) -> tuple[list, str] | None:
        """获取最近一次搜索结果 + 原始查询。"""
        entry = self._store.get(session_id)
        if entry is None:
            return None
        ts, results, query = entry
        if time.time() - ts > self.ttl:
            del self._store[session_id]
            return None
        return results, query
