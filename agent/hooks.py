"""Hooks 生命周期模块。

允许在 Agent 或工具调用的关键节点执行外部命令，例如自动运行 linter。
Hook 通过配置文件启用，失败不会中断主流程，但会返回执行结果。
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class HookTrigger(str, Enum):
    """Agent 支持的生命周期触发点。"""

    BEFORE_AGENT = "before_agent"
    AFTER_AGENT = "after_agent"
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"
    ON_ERROR = "on_error"


@dataclass(slots=True)
class HookConfig:
    """单条 Hook 配置。"""

    trigger: HookTrigger
    command: str
    timeout: float = 10.0
    enabled: bool = True


class HookSystem:
    """根据触发点执行已启用 Hook。"""

    def __init__(self, hooks: list[HookConfig], cwd: Path) -> None:
        self.hooks = hooks
        self.cwd = cwd

    async def trigger(self, trigger: HookTrigger, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """执行指定触发点的所有 Hook，并返回结果列表。"""
        results: list[dict[str, Any]] = []
        for hook in self.hooks:
            if not hook.enabled or hook.trigger != trigger:
                continue
            env = os.environ.copy()
            env["AI_AGENT_CURRENT_WORKING_DIRECTORY"] = str(self.cwd)
            for key, value in (context or {}).items():
                env[f"AI_AGENT_{key.upper()}"] = str(value)
            try:
                proc = await asyncio.create_subprocess_shell(
                    hook.command,
                    cwd=self.cwd,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=hook.timeout)
                results.append(
                    {
                        "command": hook.command,
                        "returncode": proc.returncode,
                        "stdout": stdout.decode(errors="replace"),
                        "stderr": stderr.decode(errors="replace"),
                    }
                )
            except Exception as exc:
                results.append({"command": hook.command, "error": str(exc)})
        return results


def build_hook_system(items: list[dict[str, Any]], cwd: Path) -> HookSystem:
    """从配置字典构建 HookSystem，非法配置会被跳过。"""
    hooks: list[HookConfig] = []
    for item in items:
        try:
            hooks.append(
                HookConfig(
                    trigger=HookTrigger(item["trigger"]),
                    command=item["command"],
                    timeout=float(item.get("timeout", 10.0)),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        except (KeyError, ValueError):
            continue
    return HookSystem(hooks, cwd)
