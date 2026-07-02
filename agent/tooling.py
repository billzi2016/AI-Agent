"""工具系统基础模块。

定义所有工具必须遵守的抽象接口、工具类型枚举、统一返回值和注册表。
Agent loop 只和 `ToolRegistry` 交互，不需要知道每个具体工具的实现细节。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ToolKind(str, Enum):
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    NETWORK = "network"
    MEMORY = "memory"
    MCP = "mcp"


@dataclass(slots=True)
class ToolResult:
    """工具执行结果的统一结构，方便成功和失败都用同一条链路返回给模型。"""
    success: bool
    content: str
    metadata: dict[str, Any] | None = None

    @classmethod
    def success_result(cls, content: str, metadata: dict[str, Any] | None = None) -> "ToolResult":
        return cls(True, content, metadata)

    @classmethod
    def error_result(cls, content: str, metadata: dict[str, Any] | None = None) -> "ToolResult":
        return cls(False, content, metadata)


class Tool(ABC):
    """所有工具的抽象基类。"""
    name: str
    description: str
    kind: ToolKind

    @abstractmethod
    def schema(self) -> dict[str, Any]:
        raise NotImplementedError

    def validate(self, params: dict[str, Any]) -> None:
        """参数校验钩子；复杂工具可以重写，默认不做额外校验。"""
        return None

    def is_mutating(self) -> bool:
        """标记工具是否会改变外部状态，审批系统会用到。"""
        return self.kind in {ToolKind.WRITE, ToolKind.SHELL}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError


class ToolRegistry:
    """工具注册表，负责注册、列出、生成 schema 和统一调用工具。"""
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": tool.schema()} for tool in self.list_tools()]

    async def invoke(self, name: str, params: dict[str, Any]) -> ToolResult:
        """按名称调用工具，并把异常统一包装成 ToolResult。"""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult.error_result(f"Unknown tool: {name}")
        try:
            tool.validate(params)
            return await tool.execute(**params)
        except Exception as exc:
            return ToolResult.error_result(f"{type(exc).__name__}: {exc}")
