"""
AstrBot 联网搜索插件 — 本地测试脚本
运行方式: cd astrbot-web-search && python test.py

无需 AstrBot 环境，直接测试核心功能。
LLM 测试需要有效的 API Key（可选，跳过不影响其他测试）。
"""
import io
import sys
# 解决 Windows GBK 终端编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════════════════════════
# 测试 1: 搜索缓存
# ═══════════════════════════════════════════════════════════════
def test_cache():
    from cache import SearchCache

    print("── 测试 1: 搜索缓存 ──")
    c = SearchCache(ttl=2)

    assert c.get("test") is None, "空缓存应返回 None"
    c.set("test", [{"title": "结果1"}])
    assert c.get("test") is not None, "写入后应命中"
    assert c.get("test")[0]["title"] == "结果1", "应返回正确结果"

    import time
    time.sleep(2.1)
    assert c.get("test") is None, "过期后应返回 None"

    print("  [OK] 缓存读写、过期均正常")


# ═══════════════════════════════════════════════════════════════
# 测试 2: 频率限制
# ═══════════════════════════════════════════════════════════════
def test_rate_limiter():
    from cache import RateLimiter

    print("── 测试 2: 频率限制 ──")
    limiter = RateLimiter(max_requests=3, window=60)

    user = "test_user_001"
    assert limiter.check(user) is True, "前 3 次应放行"
    assert limiter.check(user) is True
    assert limiter.check(user) is True
    assert limiter.check(user) is False, "第 4 次应拦截"

    print("  [OK] 频率限制正常")


# ═══════════════════════════════════════════════════════════════
# 测试 3: 对话上下文存储
# ═══════════════════════════════════════════════════════════════
def test_conversation():
    from cache import ConversationStore

    print("── 测试 3: 多轮对话上下文 ──")
    store = ConversationStore(ttl=60)

    results = [{"title": "搜索结果"}]
    store.save("session_1", "天气怎么样", results)
    saved = store.get("session_1")
    assert saved is not None, "存储后应能获取"
    assert saved[0] == results, "结果应一致"
    assert saved[1] == "天气怎么样", "查询应一致"

    assert store.get("unknown_session") is None, "未存储应返回 None"

    print("  [OK] 对话上下文正常")


# ═══════════════════════════════════════════════════════════════
# 测试 4: DuckDuckGo 搜索（免费，无需 API Key）
# ═══════════════════════════════════════════════════════════════
async def test_ddg_search():
    print("── 测试 4: DuckDuckGo 搜索 ──")
    try:
        from search_engines.duckduckgo import DuckDuckGoEngine
    except ImportError as e:
        print(f"  [SKIP] 缺少依赖: {e}")
        return

    try:
        engine = DuckDuckGoEngine()
        resp = await engine.search("Python 3.13 new features", max_results=3)
    except Exception as e:
        print(f"  [SKIP] 搜索不可用: {e}")
        print(f"  运行: pip install -r requirements.txt")
        return

    if resp.error:
        print(f"  [WARN] 搜索失败: {resp.error}")
        print("  (DDG 可能被限流，不影响其他测试)")
        return

    if not resp.results:
        print("  [WARN] 搜索返回空结果（DDG 可能被限流）")
        return

    print(f"  [OK] DDG 搜索成功，返回 {len(resp.results)} 条结果")
    for i, r in enumerate(resp.results, 1):
        print(f"     [{i}] {r.title[:50]}...")
        print(f"         {r.url}")


# ═══════════════════════════════════════════════════════════════
# 测试 5: 搜索引擎回退链路
# ═══════════════════════════════════════════════════════════════
async def test_fallback_chain():
    print("── 测试 5: 回退链路 ──")
    try:
        from search_engines import SearchRouter
    except ImportError as e:
        print(f"  [SKIP] 缺少依赖: {e}")
        return

    try:
        config = {}
        router = SearchRouter(
            primary="duckduckgo",
            config=config,
            fallback_chain=["duckduckgo", "bing", "google"],
        )
        resp = await router.search("hello world", max_results=2)
    except Exception as e:
        print(f"  [SKIP] 搜索不可用: {e}")
        return

    if resp.results:
        print(f"  [OK] 回退链路搜索成功，引擎: {resp.engine}")
    elif resp.error:
        print(f"  [WARN] 所有引擎失败: {resp.error}")
    else:
        print(f"  [WARN] 无结果")


# ═══════════════════════════════════════════════════════════════
# 测试 6: LLM 提供者（需要有效 API Key）
# ═══════════════════════════════════════════════════════════════
async def test_llm_provider():
    print("── 测试 6: LLM 提供者 ──")

    try:
        from llm_providers import create_provider
        import yaml
    except ImportError as e:
        print(f"  [SKIP] 缺少依赖: {e}")
        print(f"  运行: pip install -r requirements.txt")
        return

    # 尝试读取本地 config.yaml
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

    provider_type = config.get("llm_provider", "openai")
    api_key = config.get("llm_api_key") or config.get("anthropic_api_key") or config.get("gemini_api_key", "")

    if not api_key:
        print(f"  [SKIP] 未配置 API Key，跳过 LLM 测试")
        print(f"  请在 config.yaml 中填入对应 API Key 后重新运行")
        return

    try:
        provider = create_provider(provider_type, config)
    except Exception as e:
        print(f"  [FAIL] 创建提供者失败: {e}")
        return

    # 用简单判断测试连通性
    print(f"  测试 {provider_type} -> 判断是否搜索...")
    try:
        result = await provider.should_search("今天北京天气怎么样")
        print(f"  判断结果: {'需要搜索' if result else '不需要搜索'}")
        print(f"  [OK] LLM ({provider_type}) 连通正常")
    except Exception as e:
        print(f"  [FAIL] LLM 调用失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 测试 7: 格式化工具
# ═══════════════════════════════════════════════════════════════
def test_formatting():
    from llm_providers.base import format_results, format_citations, fallback_text

    print("── 测试 7: 格式化工具 ──")

    from search_engines.base import SearchResult
    results = [
        SearchResult(title="Test 1", url="https://example.com/1", snippet="Snippet 1"),
        SearchResult(title="Test 2", url="https://example.com/2", snippet="Snippet 2"),
    ]

    fmt = format_results(results)
    assert "Test 1" in fmt and "example.com" in fmt, "format_results 应包含结果"

    cit = format_citations(results)
    assert "查自" in cit and "Test 1" in cit, "format_citations 应包含来源"

    fb = fallback_text(results)
    assert "Test 1" in fb and "帮" in fb, "fallback_text 应包含结果"

    print("  [OK] 格式化工具正常")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════
async def main():
    print("=" * 60)
    print("  AstrBot 联网搜索插件 — 本地测试")
    print("=" * 60)

    # 纯逻辑测试（无需网络）
    test_cache()
    test_rate_limiter()
    test_conversation()
    test_formatting()

    print()

    # 网络测试
    print("── 网络测试 ──")
    await test_ddg_search()
    import time; time.sleep(1)  # 避免 DDG 连续请求限流
    await test_fallback_chain()

    print()

    # LLM 测试（需要 API Key）
    await test_llm_provider()

    print()
    print("=" * 60)
    print("  全部测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
