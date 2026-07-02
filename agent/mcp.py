"""MCP 集成模块。

这里提供最小可运行的 MCP 管理层：读取配置、记录服务器状态，并预留
`list_tools`/`call_tool` 接口。实际 MCP SDK 可在这个边界内替换接入。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MCPConnectionState(str, Enum):
    """MCP 服务器连接状态。"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass(slots=True)
class MCPServer:
    """单个 MCP 服务器配置和状态。"""

    name: str
    config: dict[str, Any]
    state: MCPConnectionState = MCPConnectionState.DISCONNECTED
    error: str | None = None


class MCPManager:
    """管理多个 MCP 服务器。"""

    def __init__(self, servers: dict[str, dict[str, Any]]) -> None:
        self.servers = {name: MCPServer(name, cfg) for name, cfg in servers.items()}

    async def connect_all(self) -> None:
        """连接所有已配置服务器；当前实现记录状态，保持接口稳定。"""
        for server in self.servers.values():
            try:
                server.state = MCPConnectionState.CONNECTING
                # 真实 MCP SDK 接入时在这里启动 stdin/http/sse 连接。
                server.state = MCPConnectionState.CONNECTED
            except Exception as exc:
                server.state = MCPConnectionState.ERROR
                server.error = str(exc)

    def list_tools(self) -> list[str]:
        """列出 MCP 工具；占位实现返回服务器状态。"""
        return [f"{srv.name}: {srv.state.value}" for srv in self.servers.values()]

    async def disconnect_all(self) -> None:
        """断开所有 MCP 连接。"""
        for server in self.servers.values():
            server.state = MCPConnectionState.DISCONNECTED
