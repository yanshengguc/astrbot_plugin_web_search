import os
import sys
import re
import time
import asyncio

# 确保 AstrBot 能找到插件目录下的子模块
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

import yaml

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from search_engines import SearchRouter
from llm_providers import create_provider
from cache import SearchCache, RateLimiter, ConversationStore

CONFIG_TEMPLATE = {
    # 搜索引擎
    "search_engine": "duckduckgo",
    "fallback_chain": ["duckduckgo", "bing", "google"],
    "bing_api_key": "",
    "google_api_key": "",
    "google_cse_id": "",
    # LLM — 选择提供商
    "llm_provider": "openai",
    # OpenAI / DeepSeek / Ollama / 硅基流动 等
    "llm_base_url": "https://api.openai.com/v1",
    "llm_api_key": "",
    "llm_model": "gpt-4o",
    # Anthropic Claude
    "anthropic_api_key": "",
    "anthropic_model": "claude-sonnet-4-6",
    # Google Gemini
    "gemini_api_key": "",
    "gemini_model": "gemini-2.0-flash",
    # 功能开关
    "enable_command": True,
    "enable_auto_search": True,
    "enable_auto_detect": True,
    "enable_llm_judge": False,
    "enable_followup": True,
    "auto_detect_min_len": 5,
    "auto_detect_cooldown": 0,
    # 参数
    "max_results": 5,
    "search_timeout": 15,
    "cache_ttl": 300,
    "rate_limit_max": 8,
    "rate_limit_window": 60,
    "followup_ttl": 600,
}

_AT_RE = re.compile(r"\[CQ:at,\s*qq=\d+\s*\]")

# 明确请求帮助搜索的句式
_EXPLICIT_SEARCH_RE = (
    r"(帮(我|忙|个忙)[搜查找])"           # 帮我搜 / 帮忙查 / 帮我找
    r"|([搜查找]一下)"                      # 搜一下 / 查一下
    r"|(你[能给].*[搜查找])"               # 你能帮我找找
    r"|([搜查找][搜查找])"                  # 搜搜 / 查查 / 找找
    r"|(不对|错了|不是|重新[搜查找]|再[搜查找])"  # 纠正 / 重新查
    r"|(你.{0,4}能.{0,4}联网)"             # 你能联网吗
    r"|(你.{0,4}有.{0,4}联网)"             # 你有没有联网
    r"|(你.{0,4}联网)"                      # 你联网没 / 你联网了吗
)

def _load_config(context: Context) -> dict:
    config_path = os.path.join(_plugin_dir, "config.yaml")

    config = dict(CONFIG_TEMPLATE)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            config.update(user_config)
        except Exception as e:
            logger.warning(f"[WebSearch] 配置读取失败: {e}")

    if not os.path.exists(config_path):
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    CONFIG_TEMPLATE, f, allow_unicode=True, default_flow_style=False
                )
            logger.info(f"[WebSearch] 已创建默认配置: {config_path}")
        except Exception as e:
            logger.warning(f"[WebSearch] 创建配置文件失败: {e}")

    return config


def _flatten_config(cfg: dict) -> dict:
    """将 _conf_schema 的嵌套分组配置扁平化为一级键值对。

    AstrBot 的 object 分组会产生如 {'llm': {'llm_provider': ...}} 的嵌套结构，
    而旧 config.yaml 已经是扁平的 {'llm_provider': ...}。
    此函数自动兼容两种格式。
    """
    flat = {}
    group_names = {"llm", "alt_llm", "search", "features", "advanced"}
    for key, value in cfg.items():
        if key in group_names and isinstance(value, dict):
            # 分组对象 → 展开子字段
            for sub_key, sub_value in value.items():
                flat[sub_key] = sub_value
        else:
            flat[key] = value
    return flat


def _is_search_likely(message: str) -> bool:
    """判断消息是否需要搜索。反向过滤——只排除明显不需要搜的闲聊。"""
    msg = message.strip()
    if len(msg) < 2 or msg.startswith("/"):
        return False

    # 纯闲聊/语气词/日常寒暄
    if re.fullmatch(
        r"(好|好的|好滴|嗯|哦|啊|哈|嗨|hi|hello|早|晚安|再见|拜|谢|ok|OK"
        r"|行|对|是|可以|不错|厉害|牛|6+|[哈哈呵呵嘿嘿嘻]+"
        r"|收到|知道了|懂了|没问题|okok"
        r"|吃了吗|吃了没|吃饭了|吃饭没|睡了吗|在吗|在不在"
        r")",
        msg,
    ):
        return False

    # 单字不搜
    if len(msg) <= 1:
        return False

    return True


def _clean_msg(msg: str) -> str:
    msg = _AT_RE.sub("", msg)
    msg = re.sub(r"\[CQ:\w+[^\]]*\]", "", msg)
    return msg.strip()


def _session_id(event: AstrMessageEvent) -> str:
    """获取会话 ID，用于多轮对话和限流。"""
    sid = getattr(event, "session_id", None)
    if sid:
        return sid
    # fallback: group_id + user_id
    gid = getattr(event, "group_id", "private")
    uid = event.get_sender_id()
    return f"{gid}:{uid}"


@register(
    name="astrbot_plugin_web_search",
    author="yansheng",
    desc="AstrBot智能联网搜索 — 多引擎回退 + LLM搜索词优化 + 缓存 + 多轮追问",
    version="1.3.0",
)
class WebSearchPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)

        # 优先用 AstrBot WebUI 配置（来自 _conf_schema.json），
        # 没有则回退到 config.yaml 文件
        if config and isinstance(config, dict) and len(config) > 0:
            self.config = dict(CONFIG_TEMPLATE)
            # 扁平化：_conf_schema 的分组字段是嵌套的，展开后再合并
            self.config.update(_flatten_config(config))
        else:
            self.config = _load_config(context)
        # WebUI 保存为逗号分隔字符串，config.yaml 是列表，兼容两种格式
        fb = self.config.get("fallback_chain", ["duckduckgo", "bing", "google"])
        if isinstance(fb, str):
            fb = [e.strip() for e in fb.split(",") if e.strip()]
        self.router = SearchRouter(
            primary=self.config["search_engine"],
            config=self.config,
            fallback_chain=fb,
        )
        self.llm = create_provider(
            self.config.get("llm_provider", "openai"),
            self.config,
        )
        self.cache = SearchCache(ttl=self.config["cache_ttl"])
        self.limiter = RateLimiter(
            max_requests=self.config["rate_limit_max"],
            window=self.config["rate_limit_window"],
        )
        self.conv = ConversationStore(ttl=self.config["followup_ttl"])
        self._last_auto_search: dict[str, float] = {}

        logger.info(
            f"[WebSearch] v1.3 已加载 | 引擎: {self.config['search_engine']} "
            f"| LLM: {self.config.get('llm_provider', 'openai')} "
            f"| 模型: {self.config.get('llm_model', self.config.get('gemini_model', 'unknown'))} "
            f"| 追问: {self.config['enable_followup']}"
        )

        # ── 指令触发 /search ────────────────────────────────────
    @filter.command("search")
    async def cmd_search(self, event: AstrMessageEvent) -> MessageEventResult:
        if not self.config["enable_command"]:
            return

        query = _clean_msg(event.message_str.replace("/search", "", 1).strip())

        if not query:
            yield event.plain_result("想让我搜什么？比如 /search 今天天气")
            return

        async for result in self._handle_search(query, event):
            yield result

    # ── 明确搜索请求 ──────────────────────────────────────
    @filter.regex(_EXPLICIT_SEARCH_RE)
    async def on_explicit_search(self, event: AstrMessageEvent) -> MessageEventResult:
        """用户明确要求搜索，如 帮我搜XX / 查一下XX"""
        if not self.config["enable_auto_search"]:
            return

        message = _clean_msg(event.message_str)
        if not message:
            return

        query = self._extract_query(message)
        if not query:
            return

        async for result in self._handle_search(query, event):
            yield result

    # ── 自动搜索 ──────────────────────────────────────
    @filter.event_message_type(EventMessageType.ALL)
    async def on_auto_search(self, event: AstrMessageEvent) -> MessageEventResult:
        """检测到可能是 AI 答不上来的问题时，预先搜索并把结果注入 LLM 上下文"""
        if not self.config.get("enable_auto_detect", True):
            return
        # LLM 智能判断模式启用时，交给 on_llm_judge 处理，避免重复触发
        if self.config.get("enable_llm_judge", False):
            return

        message = _clean_msg(event.message_str)
        min_len = self.config.get("auto_detect_min_len", 5)
        if not message or len(message) < min_len or message.startswith("/"):
            return

        # 冷却检查
        cooldown = self.config.get("auto_detect_cooldown", 0)
        sid = _session_id(event)
        if cooldown > 0:
            last = self._last_auto_search.get(sid, 0)
            if time.time() - last < cooldown:
                return

        # 只有看起来像在问问题时才搜索
        if not _is_search_likely(message):
            return

        # 是明确指令的交给 explicit search handler，不重复处理
        if re.search(_EXPLICIT_SEARCH_RE, message):
            return

        # 追问优先
        fu = await self._check_followup(event)
        if fu:
            async for r in self._do_followup(*fu, event):
                yield r
            return

        logger.info(f"[WebSearch] 预搜索: {message[:60]}...")

        # 执行搜索
        max_results = self.config.get("max_results", 5)
        cached = self.cache.get(message)
        if cached:
            results = cached
        else:
            try:
                search_response = await asyncio.wait_for(
                    self.router.search(message, max_results=max_results),
                    timeout=self.config.get("search_timeout", 15),
                )
                if search_response.error or not search_response.results:
                    return
                results = search_response.results
                self.cache.set(message, results)
                self.conv.save(_session_id(event), message, results)
            except Exception as e:
                logger.warning(f"[WebSearch] 预搜索失败: {e}")
                return

        if cooldown > 0:
            self._last_auto_search[sid] = time.time()
        async for r in self._respond_with_results(message, results, event):
            yield r

    # ── LLM 智能判断（可选） ────────────────────────────────
    @filter.event_message_type(EventMessageType.ALL)
    async def on_llm_judge(self, event: AstrMessageEvent) -> MessageEventResult:
        if not self.config.get("enable_llm_judge", False):
            return

        message = _clean_msg(event.message_str)
        min_len = self.config.get("auto_detect_min_len", 10)
        if not message or len(message) < min_len or message.startswith("/"):
            return
        # 明确搜索请求交给 on_explicit_search 处理，不重复触发
        if re.search(_EXPLICIT_SEARCH_RE, message):
            return

        fu = await self._check_followup(event)
        if fu:
            async for r in self._do_followup(*fu, event):
                yield r
            return

        should = await self.llm.should_search(message)
        if not should:
            return

        logger.info(f"[WebSearch] LLM 判断需要搜索: {message[:60]}...")
        yield event.plain_result("这我得查一下，稍等~")
        async for result in self._handle_search(message, event):
            yield result

    # ── 辅助方法 ──────────────────────────────────────────

    def _extract_query(self, message: str) -> str:
        """从消息中提取真正的搜索词（去掉触发短语）。"""
        # 用户问机器人自己有没有联网 → 搜点东西证明能力
        if re.search(r"(你.{0,4}(能|有).{0,4}联网|你.{0,4}联网)", message):
            return "今天是什么日子"

        triggers = [
            r"帮(我|忙|个忙)[搜查找](一下|下|一查|一搜)?",
            r"[搜查找]一下",
            r"你[能给].*?[搜查找](一下|下|查|搜)?",
            r"[搜查找][搜查找]",
            r"(不对|错了|不是|重新[搜查找]|再[搜查找])",
        ]
        for pat in triggers:
            m = re.search(pat, message)
            if m:
                q = message[:m.start()] + message[m.end():]
                q = q.strip().strip("，。, .!！?？")
                # 去掉尾部语气词
                q = re.sub(r"[呢吧啊呀嘛哦咯喔哈哟嘞诶哇]+$", "", q).strip()
                return q
        return message.strip()

    async def _check_followup(self, event: AstrMessageEvent) -> tuple | None:
        """检测追问，返回 (prev_results, prev_query) 或 None。"""
        if not self.config["enable_followup"]:
            return None
        sid = _session_id(event)
        prev = self.conv.get(sid)
        if not prev:
            return None
        prev_results, prev_query = prev
        message = _clean_msg(event.message_str)
        is_fu = await self.llm.is_followup(message, prev_query)
        if not is_fu:
            return None
        return (prev_results, prev_query)

    async def _do_followup(self, prev_results, prev_query, event):
        """执行追问回复。"""
        message = _clean_msg(event.message_str)
        logger.info(f"[WebSearch] 检测到追问: {message[:50]}...")
        async for r in self._respond_with_results(
            message, prev_results, event, is_followup=True, prev_query=prev_query
        ):
            yield r

    # ── 搜索结果回复 ──────────────────────────────────────
    async def _respond_with_results(self, query, results, event,
                                    is_followup=False, prev_query=""):
        """将搜索结果交给 AstrBot 主 LLM，用人设自然回复。"""

        # 去重：按 URL 只保留第一条出现的
        seen = set()
        deduped = []
        for r in results:
            if r.url not in seen:
                seen.add(r.url)
                deduped.append(r)

        if not deduped:
            yield event.plain_result("没搜到相关内容，换个关键词试试？")
            return

        from llm_providers.base import format_results
        results_text = format_results(deduped)

        if is_followup:
            prompt = (
                f"朋友之前问「{prev_query}」，你帮他查到这些：\n{results_text}\n\n"
                f"现在他追问「{query}」，像平时聊天一样自然回答他。"
                f"不要提你查过资料，就像你本来就懂一样聊。"
            )
        else:
            prompt = (
                f"朋友问你「{query}」，你私下查到这些资料：\n{results_text}\n\n"
                f"像平时聊天一样自然地告诉他。不要说你查过、搜过、找到什么——"
                f"就像你本来就知道一样，用你自己的说话方式回答。"
            )

        yield event.request_llm(prompt=prompt)

    # ── 核心搜索处理 ────────────────────────────────────────
    async def _handle_search(self, query: str, event: AstrMessageEvent):
        """统一搜索入口：限流 → 优化 → 缓存 → 搜索 → LLM 总结。"""

        # 1. 频率限制
        uid = _session_id(event)
        if not self.limiter.check(uid):
            yield event.plain_result(
                "你问得太快了，让我喘口气，等下再问我吧~"
            )
            return

        # 2. LLM 优化搜索词
        search_query = query
        has_key = any([
            self.config.get("llm_api_key"),
            self.config.get("anthropic_api_key"),
            self.config.get("gemini_api_key"),
        ])
        if has_key and len(query) > 4:
            try:
                optimized = await asyncio.wait_for(
                    self.llm.optimize_query(query), timeout=5
                )
                if optimized and optimized != query:
                    logger.info(f"[WebSearch] 搜索词优化: {query[:30]} → {optimized[:30]}")
                    search_query = optimized
            except Exception:
                pass  # 优化失败用原词，不影响搜索

        # 3. 缓存检查
        cached = self.cache.get(search_query)
        if cached:
            logger.info(f"[WebSearch] 缓存命中: {search_query[:40]}")
            async for r in self._respond_with_results(query, cached, event):
                yield r
            self.conv.save(_session_id(event), query, cached)
            return

        # 4. 执行搜索（带回退）
        max_results = self.config.get("max_results", 5)
        try:
            search_response = await asyncio.wait_for(
                self.router.search(search_query, max_results=max_results),
                timeout=self.config.get("search_timeout", 15),
            )
        except asyncio.TimeoutError:
            yield event.plain_result("搜了好久没结果，可能是网络不好，等下再试试？")
            return
        except Exception as e:
            logger.error(f"[WebSearch] 搜索异常: {e}")
            yield event.plain_result(f"搜索出错了，晚点再试试吧。")
            return

        if search_response.error:
            logger.warning(f"[WebSearch] 搜索错误: {search_response.error}")
            yield event.plain_result(f"搜了一下没找到结果... {search_response.error}")
            return

        if not search_response.results:
            yield event.plain_result(f"搜了一圈，没找到和「{query}」相关的内容，换个关键词试试？")
            return

        logger.info(
            f"[WebSearch] 搜索完成 | 引擎: {search_response.engine} "
            f"| 结果: {len(search_response.results)} 条"
        )

        # 5. 写入缓存（按搜索词）和多轮上下文（按原问题）
        self.cache.set(search_query, search_response.results)
        self.conv.save(_session_id(event), query, search_response.results)

        # 6. 总结并回复（原问题 + 搜索结果 → AstrBot 主 LLM）
        async for r in self._respond_with_results(query, search_response.results, event):
            yield r

    # ── 生命周期 ────────────────────────────────────────────
    async def terminate(self):
        logger.info("[WebSearch] 插件已卸载")
