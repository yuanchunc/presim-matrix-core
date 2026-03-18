"""
Gemini 适配实现

基于 google-generativeai SDK，优先适配 Gemini 1.5 Pro/Flash。
支持通过环境变量 GOOGLE_API_KEY 或 GEMINI_API_KEY 配置。
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

# 环境变量名
ENV_API_KEY = "GOOGLE_API_KEY"
ENV_API_KEY_ALT = "GEMINI_API_KEY"


def _get_api_key(api_key: Optional[str] = None) -> str:
    """从入参或环境变量获取 API Key"""
    key = api_key or os.environ.get(ENV_API_KEY) or os.environ.get(ENV_API_KEY_ALT)
    if not key:
        raise LLMAuthError(
            f"未配置 Gemini API Key，请设置环境变量 {ENV_API_KEY} 或 {ENV_API_KEY_ALT}，或传入 api_key 参数"
        )
    return key


def _map_exception(e: Exception) -> Exception:
    """将 SDK 异常映射为自定义异常"""
    err_str = str(e).lower()
    if "api_key" in err_str or "invalid" in err_str or "401" in err_str or "403" in err_str:
        return LLMAuthError(f"鉴权失败: {e}", cause=e)
    if "quota" in err_str or "resource exhausted" in err_str or "429" in err_str:
        return LLMQuotaExhaustedError(f"额度耗尽或限流: {e}", cause=e)
    if "timeout" in err_str or "timed out" in err_str:
        return LLMTimeoutError(f"请求超时: {e}", cause=e)
    return LLMAPIError(f"API 调用失败: {e}", cause=e)


class GeminiAdapter(BaseLLMAdapter):
    """
    Google Gemini 适配器

    使用 google-generativeai 库，支持 Gemini 1.5 Pro/Flash 等模型。
    支持同步、流式、异步三种调用方式。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        base_url: Optional[str] = None,
        timeout: int = BaseLLMAdapter.DEFAULT_TIMEOUT,
        retry_count: int = BaseLLMAdapter.DEFAULT_RETRY_COUNT,
    ) -> None:
        """
        初始化 Gemini 适配器

        Args:
            api_key: API 密钥，None 时从环境变量 GOOGLE_API_KEY 或 GEMINI_API_KEY 读取
            model: 模型名称，如 gemini-1.5-flash、gemini-1.5-pro
            base_url: 自定义 API 地址 (可选，用于代理)
            timeout: 请求超时秒数
            retry_count: 失败时重试次数
        """
        self._api_key = _get_api_key(api_key)
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._retry_count = retry_count
        self._model_instance: Any = None

    def _get_model(self) -> Any:
        """延迟初始化并返回 GenerativeModel 实例"""
        if self._model_instance is None:
            import google.generativeai as genai

            genai.configure(api_key=self._api_key)
            if self._base_url:
                try:
                    from google.api_core.client_options import ClientOptions

                    genai.configure(
                        api_key=self._api_key,
                        transport="rest",
                        client_options=ClientOptions(api_endpoint=self._base_url),
                    )
                except Exception:
                    logger.warning("自定义 base_url 可能不被当前 SDK 支持，将使用默认端点")
            self._model_instance = genai.GenerativeModel(self._model)
        return self._model_instance

    def _build_generation_config(
        self,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> dict:
        """构建生成配置字典，兼容不同 SDK 版本"""
        return {
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_tokens,
        }

    @property
    def provider(self) -> str:
        return "gemini"

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
        """同步调用 Gemini generate_content"""
        def _call() -> str:
            try:
                model = self._get_model()
                gen_config = self._build_generation_config(temperature, top_p, max_tokens)
                full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
                response = model.generate_content(
                    full_prompt,
                    generation_config=gen_config,
                )
                if not response.text:
                    raise LLMAPIError("Gemini 返回空内容")
                return response.text
            except LLMAuthError:
                raise
            except LLMQuotaExhaustedError:
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
        """流式调用 Gemini generate_content(stream=True)"""
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt

        try:
            model = self._get_model()
            gen_config = self._build_generation_config(temperature, top_p, max_tokens)
            stream = model.generate_content(
                full_prompt,
                generation_config=gen_config,
                stream=True,
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
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

    # 测试用例：配置好 GOOGLE_API_KEY 或 GEMINI_API_KEY 后直接运行
    logging.basicConfig(level=logging.INFO)

    adapter = GeminiAdapter(model="gemini-1.5-flash")
    try:
        text = adapter.sync_chat(
            system_prompt="你是一个简洁的助手。",
            user_prompt="用一句话介绍 Gemini。",
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
            print("提示: 请设置环境变量 GOOGLE_API_KEY 或 GEMINI_API_KEY")
