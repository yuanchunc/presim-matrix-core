"""
LLM 统一接口定义

定义大模型调用的标准抽象基类 BaseLLMAdapter，
所有 LLM 适配器必须实现 sync_chat、stream_chat、async_chat 核心接口。
支持完善的异常处理与重试机制。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Generator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------


class LLMAdapterError(Exception):
    """LLM 适配器基础异常"""

    def __init__(self, message: str, cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.cause = cause


class LLMAPIError(LLMAdapterError):
    """API 调用失败 (如 4xx/5xx 响应)"""

    pass


class LLMTimeoutError(LLMAdapterError):
    """请求超时"""

    pass


class LLMAuthError(LLMAdapterError):
    """鉴权失败 (API Key 无效、过期等)"""

    pass


class LLMQuotaExhaustedError(LLMAdapterError):
    """额度耗尽 (配额用尽、限流等)"""

    pass


class LLMRateLimitError(LLMAdapterError):
    """限流 (429 Too Many Requests)"""

    pass


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------


class BaseLLMAdapter(ABC):
    """
    大模型适配器抽象基类

    所有 LLM 适配实现必须继承此类，并实现 sync_chat、stream_chat、async_chat。
    统一使用 system_prompt + user_prompt 入参，支持 temperature、top_p、max_tokens 等配置。
    """

    # 默认参数
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_TOP_P: float = 0.95
    DEFAULT_MAX_TOKENS: int = 4096
    DEFAULT_TIMEOUT: int = 60
    DEFAULT_RETRY_COUNT: int = 3

    @property
    @abstractmethod
    def provider(self) -> str:
        """厂商标识 (如 openai, gemini, qwen)"""
        pass

    @abstractmethod
    def sync_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        **kwargs: Any,
    ) -> str:
        """
        同步调用 - 返回纯文本结果

        Args:
            system_prompt: 系统提示词 (角色设定、约束等)
            user_prompt: 用户输入
            temperature: 温度参数，控制随机性 (0~2)
            top_p: 核采样参数 (0~1)
            max_tokens: 最大生成 token 数
            **kwargs: 厂商特定参数

        Returns:
            助手回复的纯文本

        Raises:
            LLMAPIError: API 调用失败
            LLMTimeoutError: 请求超时
            LLMAuthError: 鉴权失败
            LLMQuotaExhaustedError: 额度耗尽
        """
        pass

    @abstractmethod
    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """
        流式调用 - 返回逐 token 的生成器

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            temperature: 温度
            top_p: 核采样
            max_tokens: 最大 token
            **kwargs: 厂商特定参数

        Yields:
            每个 chunk 的文本片段
        """
        pass

    @abstractmethod
    async def async_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        **kwargs: Any,
    ) -> str:
        """
        异步调用 - 异步返回纯文本结果

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            temperature: 温度
            top_p: 核采样
            max_tokens: 最大 token
            **kwargs: 厂商特定参数

        Returns:
            助手回复的纯文本
        """
        pass

    def _retry_sync(
        self,
        fn: Any,
        retry_count: Optional[int] = None,
    ) -> Any:
        """
        同步重试包装 - 对可重试异常进行指数退避重试

        Args:
            fn: 无参可调用对象，如 lambda: self._call_api(...)
            retry_count: 重试次数，None 时使用 DEFAULT_RETRY_COUNT

        Returns:
            fn() 的返回值

        Raises:
            最后一次尝试的异常
        """
        count = retry_count if retry_count is not None else self.DEFAULT_RETRY_COUNT
        last_error: Optional[Exception] = None

        for attempt in range(count + 1):
            try:
                return fn()
            except (LLMTimeoutError, LLMRateLimitError, LLMAPIError) as e:
                last_error = e
                if attempt < count:
                    import time

                    delay = 2**attempt
                    logger.warning(
                        "LLM 调用失败 (尝试 %d/%d)，%s 秒后重试: %s",
                        attempt + 1,
                        count + 1,
                        delay,
                        str(e),
                    )
                    time.sleep(delay)
                else:
                    raise
            except (LLMAuthError, LLMQuotaExhaustedError) as e:
                # 鉴权、额度类错误不重试
                raise
            except Exception as e:
                last_error = e
                if attempt < count:
                    import time

                    delay = 2**attempt
                    logger.warning(
                        "LLM 调用未知错误 (尝试 %d/%d)，%s 秒后重试: %s",
                        attempt + 1,
                        count + 1,
                        delay,
                        str(e),
                    )
                    time.sleep(delay)
                else:
                    raise LLMAPIError(f"调用失败: {e}", cause=e) from e

        if last_error:
            raise last_error
        raise LLMAPIError("重试耗尽")

    async def _retry_async(
        self,
        fn: Any,
        retry_count: Optional[int] = None,
    ) -> Any:
        """
        异步重试包装 - 对可重试异常进行指数退避重试

        Args:
            fn: 无参异步可调用对象，如 lambda: self._call_api_async(...)
            retry_count: 重试次数

        Returns:
            await fn() 的返回值
        """
        import asyncio

        count = retry_count if retry_count is not None else self.DEFAULT_RETRY_COUNT
        last_error: Optional[Exception] = None

        for attempt in range(count + 1):
            try:
                return await fn()
            except (LLMTimeoutError, LLMRateLimitError, LLMAPIError) as e:
                last_error = e
                if attempt < count:
                    delay = 2**attempt
                    logger.warning(
                        "LLM 异步调用失败 (尝试 %d/%d)，%s 秒后重试: %s",
                        attempt + 1,
                        count + 1,
                        delay,
                        str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
            except (LLMAuthError, LLMQuotaExhaustedError):
                raise
            except Exception as e:
                last_error = e
                if attempt < count:
                    delay = 2**attempt
                    logger.warning(
                        "LLM 异步调用未知错误 (尝试 %d/%d)，%s 秒后重试: %s",
                        attempt + 1,
                        count + 1,
                        delay,
                        str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    raise LLMAPIError(f"调用失败: {e}", cause=e) from e

        if last_error:
            raise last_error
        raise LLMAPIError("重试耗尽")
