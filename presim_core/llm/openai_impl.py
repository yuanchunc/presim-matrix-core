"""
OpenAI 格式兼容实现

支持 OpenAI API 及所有兼容 OpenAI 接口的模型 (如 Azure OpenAI、国内代理等)。
兼容 GPT 系列及各类国内大模型。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Generator, Optional

from presim_core.llm.adapter import (
    BaseLLMAdapter,
    LLMAuthError,
    LLMAPIError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

ENV_API_KEY = "OPENAI_API_KEY"
ENV_BASE_URL = "OPENAI_BASE_URL"


def _get_api_key(api_key: Optional[str] = None) -> str:
    """从入参或环境变量获取 API Key"""
    key = api_key or os.environ.get(ENV_API_KEY)
    if not key:
        raise LLMAuthError(
            f"未配置 OpenAI API Key，请设置环境变量 {ENV_API_KEY} 或传入 api_key 参数"
        )
    return key


def _map_exception(e: Exception) -> Exception:
    """将 openai 异常映射为自定义异常"""
    err_str = str(e).lower()
    err_type = type(e).__name__.lower()

    try:
        from openai import APIError, APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

        if isinstance(e, AuthenticationError):
            return LLMAuthError(f"鉴权失败: {e}", cause=e)
        if isinstance(e, RateLimitError):
            return LLMQuotaExhaustedError(f"限流或额度耗尽: {e}", cause=e)
        if isinstance(e, APITimeoutError):
            return LLMTimeoutError(f"请求超时: {e}", cause=e)
        if isinstance(e, APIError):
            status = getattr(e, "status_code", None)
            if status == 429:
                return LLMRateLimitError(f"限流: {e}", cause=e)
            if status in (401, 403):
                return LLMAuthError(f"鉴权失败: {e}", cause=e)
            return LLMAPIError(f"API 错误: {e}", cause=e)
    except ImportError:
        pass

    if "api_key" in err_str or "401" in err_str or "403" in err_str or "authentication" in err_str:
        return LLMAuthError(f"鉴权失败: {e}", cause=e)
    if "429" in err_str or "rate" in err_str or "quota" in err_str:
        return LLMQuotaExhaustedError(f"限流或额度耗尽: {e}", cause=e)
    if "timeout" in err_str or "timed out" in err_str:
        return LLMTimeoutError(f"请求超时: {e}", cause=e)
    return LLMAPIError(f"API 调用失败: {e}", cause=e)


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI 兼容适配器

    使用 openai 库，支持 GPT 系列及所有兼容 OpenAI 格式的模型。
    可通过 base_url 配置国内代理或 Azure 端点。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        timeout: int = BaseLLMAdapter.DEFAULT_TIMEOUT,
        retry_count: int = BaseLLMAdapter.DEFAULT_RETRY_COUNT,
    ) -> None:
        """
        初始化 OpenAI 适配器

        Args:
            api_key: API 密钥，None 时从环境变量 OPENAI_API_KEY 读取
            model: 模型名称，如 gpt-4o-mini、gpt-4o、gpt-4 等
            base_url: 自定义 API 地址，用于代理或 Azure，None 时从 OPENAI_BASE_URL 读取
            timeout: 请求超时秒数
            retry_count: 失败时重试次数
        """
        self._api_key = _get_api_key(api_key)
        self._model = model
        self._base_url = base_url or os.environ.get(ENV_BASE_URL)
        self._timeout = timeout
        self._retry_count = retry_count
        self._client: Any = None

    def _get_client(self) -> Any:
        """延迟初始化 OpenAI 客户端"""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    @property
    def provider(self) -> str:
        return "openai"

    def _build_messages(self, system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
        """构建 messages 列表"""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def sync_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = BaseLLMAdapter.DEFAULT_TEMPERATURE,
        top_p: float = BaseLLMAdapter.DEFAULT_TOP_P,
        max_tokens: int = BaseLLMAdapter.DEFAULT_MAX_TOKENS,
        **kwargs: Any,
    ) -> str:
        """同步调用 OpenAI Chat Completions API"""

        def _call() -> str:
            try:
                client = self._get_client()
                messages = self._build_messages(system_prompt, user_prompt)
                response = client.chat.completions.create(
                    model=kwargs.get("model") or self._model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    **{k: v for k, v in kwargs.items() if k != "model"},
                )
                choice = response.choices[0] if response.choices else None
                if not choice or not choice.message or not choice.message.content:
                    raise LLMAPIError("OpenAI 返回空内容")
                return choice.message.content
            except (LLMAuthError, LLMQuotaExhaustedError):
                raise
            except Exception as e:
                raise _map_exception(e)

        return self._retry_sync(_call, retry_count=self._retry_count)

    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = BaseLLMAdapter.DEFAULT_TEMPERATURE,
        top_p: float = BaseLLMAdapter.DEFAULT_TOP_P,
        max_tokens: int = BaseLLMAdapter.DEFAULT_MAX_TOKENS,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式调用 OpenAI Chat Completions API"""
        try:
            client = self._get_client()
            messages = self._build_messages(system_prompt, user_prompt)
            stream = client.chat.completions.create(
                model=kwargs.get("model") or self._model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                **{k: v for k, v in kwargs.items() if k not in ("model", "stream")},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise _map_exception(e)

    async def async_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = BaseLLMAdapter.DEFAULT_TEMPERATURE,
        top_p: float = BaseLLMAdapter.DEFAULT_TOP_P,
        max_tokens: int = BaseLLMAdapter.DEFAULT_MAX_TOKENS,
        **kwargs: Any,
    ) -> str:
        """异步调用 - 使用 OpenAI 异步客户端，带重试"""

        async def _call() -> str:
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    timeout=self._timeout,
                )
                messages = self._build_messages(system_prompt, user_prompt)
                response = await client.chat.completions.create(
                    model=kwargs.get("model") or self._model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    **{k: v for k, v in kwargs.items() if k != "model"},
                )
                choice = response.choices[0] if response.choices else None
                if not choice or not choice.message or not choice.message.content:
                    raise LLMAPIError("OpenAI 返回空内容")
                return choice.message.content
            except (LLMAuthError, LLMQuotaExhaustedError):
                raise
            except Exception as e:
                raise _map_exception(e)

        return await self._retry_async(_call, retry_count=self._retry_count)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 确保项目根目录在 sys.path 中
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    logging.basicConfig(level=logging.INFO)

    adapter = OpenAIAdapter(model="gpt-4o-mini")
    try:
        text = adapter.sync_chat(
            system_prompt="你是一个简洁的助手。",
            user_prompt="用一句话介绍 GPT。",
        )
        print("sync_chat 结果:", text)

        print("stream_chat 结果:", end=" ")
        for chunk in adapter.stream_chat(
            system_prompt="你是一个简洁的助手。",
            user_prompt="数到 3。",
        ):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print("测试失败:", e)
        if "API Key" in str(e) or "api_key" in str(e).lower():
            print("提示: 请设置环境变量 OPENAI_API_KEY 或传入 api_key 参数")
