"""Agent 主循环模块。

负责一轮用户任务的完整执行：写入用户消息、调用模型、解析 tool_calls、
审批工具、执行工具、写回结果、触发 hooks，并在必要时压缩上下文。
"""

from __future__ import annotations

import json
import time
from typing import Any

from .context import compress_if_needed
from .hooks import HookTrigger
from .session import Session


async def agentic_loop(
    session: Session,
    user_message: str,
    max_turns: int = 20,
    verbose: bool = True,
) -> dict[str, Any]:
    """执行一次完整 Agent 任务，返回性能和工具调用统计。"""
    start_time = time.time()
    tools_called: list[str] = []
    compressed = False
    final_response = ""
    turn = 0

    await session.hook_system.trigger(HookTrigger.BEFORE_AGENT)
    session.ctx.add_user_message(user_message)
    session.increment_turn()

    if verbose:
        print(f"\n[Agent] User: {user_message}")
        print(f"[Agent] Registered tools: {len(session.registry.list_tools())}")

    for turn in range(max_turns):
        if await compress_if_needed(session.ctx, session.llm):
            compressed = True
            if verbose:
                print(f"[Agent] Context compressed before turn {turn + 1}.")

        try:
            tools_schema = session.registry.get_schemas() if session.registry.list_tools() else None
            response_text, usage = await session.llm.chat_completion(
                messages=session.ctx.get_messages(),
                tools=tools_schema,
            )
            session.ctx.update_usage(usage.prompt_tokens, usage.completion_tokens)
        except Exception as exc:
            await session.hook_system.trigger(HookTrigger.ON_ERROR, {"error": str(exc)})
            if verbose:
                print(f"[Agent] LLM call failed: {exc}")
            break

        if isinstance(response_text, str):
            session.ctx.add_assistant_message(response_text)
            final_response = response_text
            if verbose:
                print(f"\n[Agent] Final response:\n{response_text}")
            break

        if not isinstance(response_text, dict) or "tool_calls" not in response_text:
            final_response = str(response_text)
            session.ctx.add_assistant_message(final_response)
            break

        content = response_text.get("content", "")
        tool_calls = response_text["tool_calls"]
        session.ctx.add_assistant_message(content, tool_calls=tool_calls)

        for call in tool_calls:
            tool_name = call.get("function", {}).get("name", "")
            raw_args = call.get("function", {}).get("arguments", "{}")
            tool_id = call.get("id", "")

            try:
                params = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                params = {}

            tool = next((item for item in session.registry.list_tools() if item.name == tool_name), None)
            mutating = bool(tool and tool.is_mutating())

            if verbose:
                preview = json.dumps(params, ensure_ascii=False)[:100]
                print(f"[Agent] Tool call: {tool_name}({preview})")

            approved = await session.approval_mgr.request_approval(tool_name, params, mutating=mutating)
            if not approved:
                session.ctx.add_tool_result(tool_id, "Tool call rejected by approval policy.")
                continue

            await session.hook_system.trigger(HookTrigger.BEFORE_TOOL, {"tool_name": tool_name})

            session.loop_detector.record(tool_name, params)
            loop_result = session.loop_detector.check()
            if loop_result:
                message = f"[loop detection] {loop_result.description}\nSuggestion: {loop_result.suggestion}"
                session.ctx.add_tool_result(tool_id, message)
                if verbose:
                    print(f"[Agent] {message}")
                continue

            result = await session.registry.invoke(tool_name, params)
            tools_called.append(tool_name)
            session.ctx.add_tool_result(tool_id, result.content)

            if verbose:
                status = "ok" if result.success else "failed"
                print(f"[Agent]   -> [{status}] {result.content[:120].replace(chr(10), ' ')}")

            await session.hook_system.trigger(
                HookTrigger.AFTER_TOOL,
                {"tool_name": tool_name, "tool_success": str(result.success).lower()},
            )

    await session.hook_system.trigger(HookTrigger.AFTER_AGENT)
    elapsed = time.time() - start_time

    return {
        "response": final_response,
        "turns": turn + 1,
        "tools_called": tools_called,
        "elapsed_sec": round(elapsed, 2),
        "compressed": compressed,
        "token_usage": session.ctx.stats(),
    }
