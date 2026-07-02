"""运行时工具发现模块。

扫描 `.ai_agent/tools/*.py`，动态导入其中继承 `Tool` 的类并实例化注册。
这样用户可以扩展工具，而不需要修改 Agent 核心代码。
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any

from .tooling import Tool


class ToolDiscovery:
    """从工作目录加载自定义工具。"""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.tools_dir = cwd / ".ai_agent" / "tools"

    async def discover(self) -> list[Tool]:
        """发现并实例化所有自定义工具。"""
        if not self.tools_dir.exists():
            return []
        tools: list[Tool] = []
        for path in sorted(self.tools_dir.glob("*.py")):
            if path.name in {"__init__.py", "__main__.py"}:
                continue
            tools.extend(self._load_tools_from_file(path))
        return tools

    def _load_tools_from_file(self, path: Path) -> list[Tool]:
        """动态导入单个 Python 文件，并提取 Tool 子类。"""
        spec = importlib.util.spec_from_file_location(f"ai_agent_tool_{path.stem}", path)
        if not spec or not spec.loader:
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        found: list[Tool] = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is Tool or not issubclass(obj, Tool):
                continue
            try:
                found.append(obj())
            except TypeError:
                try:
                    found.append(obj(self.cwd))
                except TypeError:
                    continue
        return found


async def discover_and_register(registry: Any, cwd: Path) -> list[Tool]:
    """发现工具并注册到给定 registry。"""
    tools = await ToolDiscovery(cwd).discover()
    for tool in tools:
        registry.register(tool)
    return tools
