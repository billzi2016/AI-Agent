"""网络工具模块。

提供 Web 搜索和网页抓取能力。网络依赖可能不存在，因此工具内部会给出
明确错误，而不是让整个 Agent 初始化失败。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .tooling import Tool, ToolKind, ToolResult


class WebSearchTool(Tool):
    """使用 DuckDuckGo 搜索网页。"""
    name = "web_search"
    description = "Search the web with DuckDuckGo."
    kind = ToolKind.NETWORK

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        }

    async def execute(self, query: str, max_results: int = 10) -> ToolResult:
        """执行搜索，并把标题、链接和摘要整理成文本。"""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return ToolResult.error_result("Missing dependency: pip install duckduckgo-search")
        limit = min(20, max(1, int(max_results)))
        rows = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=limit):
                rows.append(f"- {item.get('title', '')}\n  {item.get('href', '')}\n  {item.get('body', '')}")
        return ToolResult.success_result("\n".join(rows), {"count": len(rows)})


class WebFetchTool(Tool):
    """抓取 HTTP/HTTPS 页面内容。"""
    name = "web_fetch"
    description = "Fetch a URL over HTTP or HTTPS."
    kind = ToolKind.NETWORK

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout": {"type": "number", "default": 120},
                },
                "required": ["url"],
            },
        }

    async def execute(self, url: str, timeout: float = 120) -> ToolResult:
        """抓取 URL；只允许 http/https，并限制返回内容大小。"""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return ToolResult.error_result("Only http and https URLs are allowed.")
        try:
            import httpx
        except ImportError:
            return ToolResult.error_result("Missing dependency: pip install httpx")
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
        text = response.text
        truncated = len(text) > 100_000
        if truncated:
            text = text[:100_000] + "\n[truncated]"
        return ToolResult.success_result(text, {"status_code": response.status_code, "truncated": truncated})


def register_network_tools(registry: Any) -> None:
    """把内置网络工具注册到工具表。"""
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
