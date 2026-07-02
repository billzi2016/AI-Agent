"""上下文管理模块。

负责保存 messages、估算 token、记录模型用量，并在上下文过长时触发压缩。
LLM 是无状态的，所以每轮请求都必须从这里取完整对话历史。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def estimate_tokens(text: str) -> int:
    """估算文本 token 数；优先使用 tiktoken，失败时用字符长度粗略估算。"""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def build_system_prompt(working_directory: str) -> str:
    """生成默认系统提示词，把当前工作目录和安全约束写进去。"""
    return (
        "You are a local AI coding agent. Work inside the configured working directory, "
        "use tools when needed, explain risky actions before taking them, and keep changes scoped. "
        f"Current working directory: {working_directory}"
    )


@dataclass(slots=True)
class ContextManager:
    """对话历史与 token 统计的集中管理器。"""
    system_prompt: str
    context_window: int = 128_000
    messages: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __post_init__(self) -> None:
        """确保第一条消息始终是 system prompt。"""
        if not self.messages:
            self.messages.append({"role": "system", "content": self.system_prompt})

    def add_user_message(self, content: str) -> None:
        """追加用户消息。"""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str, tool_calls: list[dict[str, Any]] | None = None) -> None:
        """追加助手消息；如果模型请求工具调用，也一起保存。"""
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """把工具执行结果写回上下文，供下一轮模型继续推理。"""
        self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

    def get_messages(self) -> list[dict[str, Any]]:
        """返回 OpenAI Chat API 可直接使用的 messages。"""
        return self.messages

    def clear_messages(self) -> None:
        """清空历史对话，但保留 system prompt。"""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def update_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """累加模型返回的 token 用量。"""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def total_tokens(self) -> int:
        """返回当前上下文 token 数，优先使用更保守的估算值。"""
        estimated = sum(estimate_tokens(str(m.get("content", ""))) for m in self.messages)
        return max(estimated, self.prompt_tokens + self.completion_tokens)

    def needs_compression(self) -> bool:
        """判断是否超过上下文窗口的 80%，超过则应压缩历史。"""
        return self.total_tokens() > int(self.context_window * 0.8)

    def stats(self) -> dict[str, int]:
        """返回 CLI 展示用的统计信息。"""
        return {
            "messages": len(self.messages),
            "estimated_tokens": self.total_tokens(),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


async def compress_if_needed(ctx: ContextManager, llm: Any) -> bool:
    """上下文过长时压缩较早的消息，保留最近几轮原文。"""
    if not ctx.needs_compression() or len(ctx.messages) <= 6:
        return False

    # 只压缩 system prompt 之后、最近 4 条之前的历史，避免丢失当前任务现场。
    history = "\n\n".join(f"{m.get('role')}: {m.get('content', '')}" for m in ctx.messages[1:-4])
    prompt = (
        "Summarize this conversation history for a coding agent. Preserve decisions, files changed, "
        "open tasks, constraints, and tool results that matter.\n\n"
        f"{history[:20_000]}"
    )
    summary, usage = await llm.chat_completion(
        messages=[
            {"role": "system", "content": "You compress conversations for a coding agent."},
            {"role": "user", "content": prompt},
        ]
    )
    ctx.update_usage(usage.prompt_tokens, usage.completion_tokens)
    ctx.messages = [
        ctx.messages[0],
        {"role": "system", "content": f"Compressed prior conversation:\n{summary}"},
        *ctx.messages[-4:],
    ]
    return True
