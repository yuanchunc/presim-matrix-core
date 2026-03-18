"""
通义千问 (Qwen) 适配实现

基于阿里云 dashscope SDK，适配通义千问系列模型。
支持通过环境变量 DASHSCOPE_API_KEY 配置。
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
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

ENV_API_KEY = "DASHSCOPE_API_KEY"


def _get_api_key(api_key: Optional[str] = None) -> str:
    """从入参或环境变量获取 API Key"""
    key = api_key or os.environ.get(ENV_API_KEY)
    if not key:
        raise LLMAuthError(
            f"未配置 DashScope API Key，请设置环境变量 {ENV_API_KEY} 或传入 api_key 参数"
        )
    return key


def _map_exception(e: Exception) -> Exception:
    """将 dashscope 异常映射为自定义异常"""
    err_str = str(e).lower()

    # dashscope 通过 response.status_code / response.code 表示错误
    if hasattr(e, "status_code"):
        sc = getattr(e, "status_code", None)
        if sc == 401 or sc == 403:
            return LLMAuthError(f"鉴权失败: {e}", cause=e)
        if sc == 429:
            return LLMQuotaExhaustedError(f"限流或额度耗尽: {e}", cause=e)

    if "api_key" in err_str or "invalid" in err_str or "401" in err_str or "403" in err_str:
        return LLMAuthError(f"鉴权失败: {e}", cause=e)
    if "quota" in err_str or "429" in err_str or "rate" in err_str or "limit" in err_str:
        return LLMQuotaExhaustedError(f"额度耗尽或限流: {e}", cause=e)
    if "timeout" in err_str or "timed out" in err_str:
        return LLMTimeoutError(f"请求超时: {e}", cause=e)
    return LLMAPIError(f"API 调用失败: {e}", cause=e)


class QwenAdapter(BaseLLMAdapter):
    """
    通义千问适配器

    使用 dashscope 库调用阿里云 DashScope API，
    支持 qwen-turbo、qwen-plus、qwen-max 等模型。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen-turbo",
        base_url: Optional[str] = None,
        timeout: int = BaseLLMAdapter.DEFAULT_TIMEOUT,
        retry_count: int = BaseLLMAdapter.DEFAULT_RETRY_COUNT,
    ) -> None:
        """
        初始化通义千问适配器

        Args:
            api_key: API 密钥，None 时从环境变量 DASHSCOPE_API_KEY 读取
            model: 模型名称，如 qwen-turbo、qwen-plus、qwen-max
            base_url: 自定义 API 地址 (dashscope 通常使用默认)
            timeout: 请求超时秒数
            retry_count: 失败时重试次数
        """
        self._api_key = _get_api_key(api_key)
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._retry_count = retry_count

    @property
    def provider(self) -> str:
        return "qwen"

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
        """同步调用 DashScope Generation.call"""

        def _call() -> str:
            try:
                import dashscope
                from http import HTTPStatus

                dashscope.api_key = self._api_key
                messages = self._build_messages(system_prompt, user_prompt)

                call_kwargs: dict[str, Any] = {
                    "model": kwargs.get("model") or self._model,
                    "messages": messages,
                    "result_format": "message",
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                }
                if self._base_url:
                    call_kwargs["base_url"] = self._base_url

                response = dashscope.Generation.call(**call_kwargs)

                if response.status_code != HTTPStatus.OK:
                    err_msg = f"DashScope 错误: {getattr(response, 'message', response)} (code={getattr(response, 'code', '')})"
                    if response.status_code in (401, 403):
                        raise LLMAuthError(err_msg)
                    if response.status_code == 429:
                        raise LLMQuotaExhaustedError(err_msg)
                    raise LLMAPIError(err_msg)

                output = response.output
                if not output or not hasattr(output, "choices") or not output.choices:
                    raise LLMAPIError("DashScope 返回空内容")

                msg = output.choices[0].message
                if not msg or not getattr(msg, "content", None):
                    raise LLMAPIError("DashScope 返回空内容")

                return msg.content
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
        """流式调用 DashScope Generation.call(stream=True)"""
        try:
            import dashscope
            from http import HTTPStatus

            dashscope.api_key = self._api_key
            messages = self._build_messages(system_prompt, user_prompt)

            call_kwargs: dict[str, Any] = {
                "model": kwargs.get("model") or self._model,
                "messages": messages,
                "result_format": "message",
                "stream": True,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            }
            if self._base_url:
                call_kwargs["base_url"] = self._base_url

            response_generator = dashscope.Generation.call(**call_kwargs)

            for resp in response_generator:
                if resp.status_code != HTTPStatus.OK:
                    err_msg = f"DashScope 流式错误: {getattr(resp, 'message', resp)}"
                    raise LLMAPIError(err_msg)
                output = getattr(resp, "output", None)
                if not output:
                    continue
                # 支持 output.text 或 output.choices[0].message.content 两种格式
                delta = getattr(output, "text", None)
                if delta is None and hasattr(output, "choices") and output.choices:
                    msg = output.choices[0].message
                    delta = getattr(msg, "content", None) if msg else None
                if delta:
                    yield delta
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
        """异步调用 - 在线程池中执行同步方法"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.sync_chat(
                system_prompt,
                user_prompt,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                **kwargs,
            ),
        )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 确保项目根目录在 sys.path 中
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    logging.basicConfig(level=logging.INFO)

    adapter = QwenAdapter(model="qwen-turbo")
    try:
        text = adapter.sync_chat(
            system_prompt="你是一个简洁的助手。",
            user_prompt="用一句话介绍通义千问。",
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
            print("提示: 请设置环境变量 DASHSCOPE_API_KEY")
