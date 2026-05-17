# AstrBot智能联网搜索

为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 提供强大的联网搜索能力。

## 功能

- **多引擎回退**：DuckDuckGo（免费无需Key）→ Bing → Google，主引擎失败自动切换
- **LLM搜索词优化**：搜索前用大模型将口语化问题改写为精准搜索词，提升命中率
- **智能总结**：搜索结果交给 AstrBot 主 LLM，用人设自然回复，不暴露搜索细节
- **三种触发方式**：
  - `/search` 指令：明确搜索
  - 自然句式：帮我搜/查一下/你联网没 等自动触发
  - 全自动检测：除闲聊外自动预搜索（可关闭/调节阈值）
- **多轮追问**：搜索后可持续追问细节，LLM判断是否追问
- **缓存与限流**：搜索结果缓存 + 频率限制，节省资源
- **三种LLM支持**：OpenAI兼容 / Anthropic Claude / Google Gemini
- **WebUI配置**：表单化配置，滑块调参

## 安装

1. 将整个文件夹放入 AstrBot 的 `data/plugins/` 目录
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 重启 AstrBot 或在 WebUI 插件管理启用
4. 在 WebUI 配置页填入 LLM API Key（用于搜索词优化，可选但推荐）

## 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `search_engine` | duckduckgo | 主搜索引擎，DDG免费无需Key |
| `max_results` | 5 | 每次搜索返回条数 |
| `llm_provider` | openai | LLM服务商，用于搜索词优化和追问判断 |
| `enable_auto_detect` | true | 是否自动检测隐含问题 |
| `auto_detect_min_len` | 5 | 自动搜索最小消息长度 |
| `auto_detect_cooldown` | 0 | 自动搜索冷却秒数 |

## 引擎API Key

| 引擎 | 是否需要Key |
|------|------------|
| DuckDuckGo | 免费，无需Key |
| Bing | 需 Azure Bing Search v7 API Key |
| Google | 需 Google Custom Search API Key + CSE ID |

## 依赖

- `httpx>=0.27.0`
- `openai>=1.30.0`
- `ddgs>=6.0.0`
- `pyyaml>=6.0`
