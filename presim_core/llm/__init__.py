"""
大模型统一适配层

提供统一的 LLM 调用接口，支持 OpenAI、Gemini、通义千问等多种后端。
通过 get_llm_adapter(model_type, **config) 工厂方法便捷获取适配器实例。
"""

from typing import Any

from presim_core.llm.adapter import (
    BaseLLMAdapter,
    LLMAdapterError,
    LLMAPIError,
    LLMAuthError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from presim_core.llm.gemini_impl import GeminiAdapter
from presim_core.llm.openai_impl import OpenAIAdapter
from presim_core.llm.qwen_impl import QwenAdapter

# 支持的模型类型常量
MODEL_TYPE_OPENAI = "openai"
MODEL_TYPE_GEMINI = "gemini"
MODEL_TYPE_QWEN = "qwen"

# 模型类型 -> 适配器类映射
_ADAPTER_REGISTRY: dict[str, type[BaseLLMAdapter]] = {
    MODEL_TYPE_OPENAI: OpenAIAdapter,
    MODEL_TYPE_GEMINI: GeminiAdapter,
    MODEL_TYPE_QWEN: QwenAdapter,
}


def get_llm_adapter(model_type: str, **config: Any) -> BaseLLMAdapter:
    """
    工厂方法：根据模型类型获取对应的 LLM 适配器实例

    用户只需指定 model_type，即可拿到对应适配器，无需单独初始化各实现类。

    Args:
        model_type: 模型类型，支持 "openai" | "gemini" | "qwen"
        **config: 适配器配置，将传递给对应适配器的 __init__
            - api_key: API 密钥 (可选，可从环境变量读取)
            - model: 模型名称 (如 gpt-4o-mini、gemini-1.5-flash、qwen-turbo)
            - base_url: 自定义 API 地址 (openai/gemini 支持)
            - timeout: 超时秒数
            - retry_count: 重试次数

    Returns:
        对应的 BaseLLMAdapter 实例

    Raises:
        ValueError: 不支持的 model_type

    Example:
        >>> adapter = get_llm_adapter("openai", model="gpt-4o-mini")
        >>> text = adapter.sync_chat("你是助手", "你好")
        >>>
        >>> adapter = get_llm_adapter("gemini", model="gemini-1.5-flash")
        >>> adapter = get_llm_adapter("qwen", model="qwen-turbo")
    """
    model_type_lower = model_type.lower().strip()
    if model_type_lower not in _ADAPTER_REGISTRY:
        raise ValueError(
            f"不支持的模型类型: {model_type}，可选: {list(_ADAPTER_REGISTRY.keys())}"
        )
    adapter_cls = _ADAPTER_REGISTRY[model_type_lower]
    return adapter_cls(**config)


def register_adapter(model_type: str, adapter_cls: type[BaseLLMAdapter]) -> None:
    """
    注册自定义适配器类型 (供扩展使用)

    Args:
        model_type: 模型类型标识
        adapter_cls: 继承 BaseLLMAdapter 的适配器类
    """
    _ADAPTER_REGISTRY[model_type.lower()] = adapter_cls


__all__ = [
    "BaseLLMAdapter",
    "LLMAdapterError",
    "LLMAPIError",
    "LLMAuthError",
    "LLMQuotaExhaustedError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "OpenAIAdapter",
    "GeminiAdapter",
    "QwenAdapter",
    "get_llm_adapter",
    "register_adapter",
    "MODEL_TYPE_OPENAI",
    "MODEL_TYPE_GEMINI",
    "MODEL_TYPE_QWEN",
]
