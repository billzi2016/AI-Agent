"""异步 LLM 客户端模块。

封装 OpenAI 兼容接口，默认连接本地 Ollama。其它模块只依赖这里暴露的
`chat_completion`，不直接依赖 OpenAI SDK，方便后续替换模型服务。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient:
    """OpenAI 兼容 Chat API 的轻量异步封装。"""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        max_retries: int = 3,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.max_retries = max_retries
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """延迟初始化 SDK 客户端，避免导入模块时就要求安装 openai。"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError("Missing dependency: pip install openai") from exc
            self._client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str | dict[str, Any], TokenUsage]:
        """调用模型，返回普通文本或 OpenAI 风格的 tool_calls 结构。"""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
                if tools:
                    kwargs["tools"] = tools
                response = await self._get_client().chat.completions.create(**kwargs)
                choice = response.choices[0]
                msg = choice.message
                usage = TokenUsage(
                    prompt_tokens=getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
                    completion_tokens=getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
                )
                if getattr(msg, "tool_calls", None):
                    # tool_calls 需要保留原始结构，后续 Agent loop 会继续解析执行。
                    return {
                        "content": msg.content or "",
                        "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                    }, usage
                return msg.content or "", usage
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(2**attempt)
        raise RuntimeError(f"LLM request failed after {self.max_retries} attempts: {last_error}")

    async def close(self) -> None:
        """关闭底层 HTTP 连接，交互模式退出时调用。"""
        if self._client is not None:
            await self._client.close()
            self._client = None
