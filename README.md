# AstrBot智能联网搜索

[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.0-blue)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-1.3.0-green)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

为 AstrBot 提供强大的联网搜索能力。**DuckDuckGo 免费无需 Key**，开箱即用。

## 功能

### 搜索引擎
- **多引擎回退**：DuckDuckGo（免费）→ Bing → Google，主引擎失败自动切换下一个
- **中文优化**：DDG 默认使用中文区域搜索，结果更精准
- **免 Key 可用**：DuckDuckGo 完全免费，不配任何 API Key 也能搜

### LLM 能力
- **搜索词优化**：搜之前用大模型将"最近很火的那个AI模型是啥"改写为"2026热门AI大模型"，提升命中率
- **智能总结**：搜索结果交给 AstrBot 主 LLM，用机器人人设自然回复，"像本来就知道一样聊天"
- **追问判断**：LLM 判断用户是否在追问上一轮搜索结果，追问则复用历史结果不重搜

### 触发方式
| 触发器 | 说明 | 示例 |
|--------|------|------|
| `/search` 指令 | 明确搜索指令 | `/search 今天天气` |
| 自然句式 | 帮我搜/查一下/你联网没 等 | "帮我搜一下比特币最新价格" |
| 自动检测 | 除闲聊外自动预搜索 | "Python 3.13有哪些新特性" |

### 辅助功能
- **多轮追问**：搜索后可以问"详细说说第二点""还有吗"等
- **搜索缓存**：相同搜索词 300 秒内复用结果，节省搜索和 LLM 费用
- **频率限制**：每用户每分钟最多 8 次搜索，防止滥用
- **可调阈值**：自动搜索的最小长度和冷却时间可配置
- **结果去重**：按 URL 去重，节省 LLM 上下文
- **空结果守护**：搜不到内容直接提示，不浪费 LLM token

## 安装

### 1. 下载
将本仓库整个文件夹放入 AstrBot 的插件目录：
```
data/plugins/astrbot-web-search/
```

### 2. 安装依赖
```bash
pip install httpx>=0.27.0 openai>=1.30.0 ddgs>=6.0.0 pyyaml>=6.0
```
或者：
```bash
pip install -r requirements.txt
```

### 3. 启用插件
- 重启 AstrBot，或
- WebUI → 插件管理 → 找到「AstrBot智能联网搜索」→ 启用

### 4. 配置 LLM（推荐）
插件用 LLM 做搜索词优化和追问判断。虽然不配也能搜（DDG 免费），但配置后效果更好。

WebUI → 插件管理 → AstrBot智能联网搜索 → 配置：
- **LLM 服务商**：选 `openai`（兼容 DeepSeek、Ollama、硅基流动等）
- **API Key**：填入你的 Key（DeepSeek 用户填 DeepSeek Key）
- **接口地址**：DeepSeek 填 `https://api.deepseek.com/v1`
- **模型名**：如 `deepseek-chat` 或 `gpt-4o`

## 配置说明

### 搜索引擎（search 分组）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `search_engine` | duckduckgo | 主搜索引擎：duckduckgo / bing / google |
| `fallback_chain` | duckduckgo,bing,google | 回退链路，逗号分隔 |
| `max_results` | 5 | 每次搜索返回条数（1-10） |
| `bing_api_key` | （空） | Azure Bing Search v7 API Key |
| `google_api_key` | （空） | Google Custom Search API Key |
| `google_cse_id` | （空） | Google Programmable Search Engine ID |

### LLM 配置（llm 分组）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `llm_provider` | openai | LLM 服务商：openai / anthropic / gemini |
| `llm_api_key` | （空） | API Key，OpenAI/DeepSeek 等填这里 |
| `llm_base_url` | https://api.openai.com/v1 | 接口地址，DeepSeek 填 `https://api.deepseek.com/v1` |
| `llm_model` | gpt-4o | 模型名，如 `deepseek-chat` |

### 备用 LLM（alt_llm 分组）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `anthropic_api_key` | （空） | 选 anthropic 时生效 |
| `anthropic_model` | claude-sonnet-4-6 | Claude 模型名 |
| `gemini_api_key` | （空） | 选 gemini 时生效 |
| `gemini_model` | gemini-2.0-flash | Gemini 模型名 |

### 功能开关（features 分组）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `enable_command` | true | /search 指令 |
| `enable_auto_search` | true | "帮我搜/查一下"等自然句式触发 |
| `enable_auto_detect` | true | 自动检测隐含问题并搜索 |
| `enable_llm_judge` | false | LLM 判断每条消息是否需搜索（费 token） |
| `enable_followup` | true | 多轮追问 |
| `auto_detect_min_len` | 5 | 自动搜索最小消息长度（3-50） |
| `auto_detect_cooldown` | 0 | 自动搜索冷却秒数，0 不限制（0-300） |

### 高级设置（advanced 分组）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `search_timeout` | 15 | 搜索超时秒数（5-60） |
| `cache_ttl` | 300 | 缓存有效期秒数（0-3600） |
| `rate_limit_max` | 8 | 每窗口最大搜索次数 |
| `rate_limit_window` | 60 | 限流窗口秒数 |
| `followup_ttl` | 600 | 追问上下文有效期秒数 |

## 使用示例

### /search 指令
```
用户: /search 北京今天天气
机器人: 北京今天晴，气温15-28℃，轻度污染...
```

### 自然句式触发
```
用户: 帮我搜一下Python 3.13的新特性
机器人: Python 3.13主要更新了这些...
```

### 自动检测
```
用户: 比特币现在什么价
机器人: （自动搜索后回复）目前比特币价格约...
```

### 多轮追问
```
用户: 搜一下DeepSeek-V4
机器人: DeepSeek-V4是...
用户: 和V3比有什么提升？
机器人: （复用上次搜索结果回答）相比V3主要提升在...
```

## LLM 接入示例

### DeepSeek
```
llm_provider: openai
llm_base_url: https://api.deepseek.com/v1
llm_api_key: sk-xxxxxxxx
llm_model: deepseek-chat
```

### Ollama 本地
```
llm_provider: openai
llm_base_url: http://localhost:11434/v1
llm_api_key: ollama
llm_model: qwen2.5:7b
```

### 硅基流动
```
llm_provider: openai
llm_base_url: https://api.siliconflow.cn/v1
llm_api_key: sk-xxxxxxxx
llm_model: deepseek-ai/DeepSeek-V3
```

## 目录结构

```
astrbot-web-search/
├── main.py              # 插件入口
├── metadata.yaml        # 插件声明
├── config.yaml          # 配置文件
├── _conf_schema.json    # WebUI 配置表单
├── test.py              # 本地测试脚本
├── cache.py             # 缓存/限流/上下文存储
├── search_engines/      # 搜索引擎适配层
│   ├── base.py          # 数据类 + 抽象基类
│   ├── duckduckgo.py    # DuckDuckGo（免费）
│   ├── bing.py          # Bing Web Search API
│   └── google.py        # Google Custom Search API
└── llm_providers/       # LLM 厂商适配层
    ├── base.py          # 抽象基类 + 共享 Prompt
    ├── openai.py        # OpenAI 兼容（DeepSeek/Ollama等）
    ├── anthropic.py     # Anthropic Claude
    └── gemini.py        # Google Gemini
```

## 常见问题

**Q: 不配 LLM Key 能用吗？**
A: 能搜，DDG 免费无需 Key。但搜索词优化和追问判断功能不会生效。

**Q: AstrBot 自带联网搜索和这个插件会冲突吗？**
A: 不会。插件独立运作，AstrBot 内置搜索开关不影响插件。

**Q: 搜索触发太频繁？**
A: 调大 `auto_detect_min_len`（如 15）和设置 `auto_detect_cooldown`（如 60）。

**Q: 搜索结果不相关？**
A: 确保已配置 LLM Key，插件会自动优化搜索词。或者调大 `max_results`。
