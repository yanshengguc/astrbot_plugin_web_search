from .base import BaseLLMProvider


__all__ = ["BaseLLMProvider", "create_provider"]


def create_provider(provider_type: str, config: dict) -> BaseLLMProvider:
    """根据配置创建 LLM 提供者实例。

    支持的 provider_type:
        - openai / deepseek / ollama  → OpenAICompatibleProvider
        - anthropic / claude          → AnthropicProvider
        - gemini / google             → GeminiProvider
    """
    t = provider_type.strip().lower()

    if t in ("openai", "deepseek", "ollama", "openai_compatible"):
        from .openai import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            model=config.get("llm_model", "gpt-4o"),
            api_key=config.get("llm_api_key", ""),
            base_url=config.get("llm_base_url", "https://api.openai.com/v1"),
        )

    elif t in ("anthropic", "claude"):
        from .anthropic import AnthropicProvider
        return AnthropicProvider(
            model=config.get("anthropic_model", "claude-sonnet-4-6"),
            api_key=config.get("anthropic_api_key", ""),
        )

    elif t in ("gemini", "google"):
        from .gemini import GeminiProvider
        return GeminiProvider(
            model=config.get("gemini_model", "gemini-2.0-flash"),
            api_key=config.get("gemini_api_key", ""),
        )

    else:
        raise ValueError(
            f"不支持的 LLM 提供者: {provider_type}\n"
            f"可选值: openai, anthropic, gemini (及其别名)"
        )
