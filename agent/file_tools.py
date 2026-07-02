"""文件系统工具模块。

提供读文件、写文件、精确编辑、列目录和 glob 搜索。所有路径都会限制在
工作目录内部，避免 Agent 意外读写工作区外的文件。
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from .tooling import Tool, ToolKind, ToolResult


MAX_READ_BYTES = 10 * 1024 * 1024


def resolve_inside(root: Path, user_path: str) -> Path:
    """解析用户传入路径，并确保最终路径没有逃出工作目录。"""
    candidate = (root / user_path).resolve() if not Path(user_path).is_absolute() else Path(user_path).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"Path escapes working directory: {user_path}")
    return candidate


def unified_diff(old: str, new: str, path: Path) -> str:
    """生成 unified diff，让模型和用户都能看到写入前后的差异。"""
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{path} (old)",
            tofile=f"{path} (new)",
        )
    )


class ReadFileTool(Tool):
    """读取文本文件，支持按行 offset/limit 截取。"""
    name = "read_file"
    description = "Read a text file inside the working directory."
    kind = ToolKind.READ

    def __init__(self, root: Path) -> None:
        self.root = root

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "default": 1},
                    "limit": {"type": "integer", "default": 200},
                },
                "required": ["path"],
            },
        }

    async def execute(self, path: str, offset: int = 1, limit: int = 200) -> ToolResult:
        """执行读文件；大文件和二进制文件会被拒绝。"""
        target = resolve_inside(self.root, path)
        if target.stat().st_size > MAX_READ_BYTES:
            return ToolResult.error_result("File is larger than 10 MB.")
        data = target.read_bytes()
        if b"\x00" in data[:4096]:
            return ToolResult.error_result("Binary file detected.")
        lines = data.decode("utf-8", errors="replace").splitlines()
        start = max(0, offset - 1)
        end = min(len(lines), start + max(1, limit))
        content = "\n".join(f"{i + 1:>5} {lines[i]}" for i in range(start, end))
        return ToolResult.success_result(content, {"path": str(target), "lines": end - start})


class WriteFileTool(Tool):
    """写入完整文本文件，并返回 diff。"""
    name = "write_file"
    description = "Write a text file inside the working directory."
    kind = ToolKind.WRITE

    def __init__(self, root: Path) -> None:
        self.root = root

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "create_directories": {"type": "boolean", "default": True},
                },
                "required": ["path", "content"],
            },
        }

    async def execute(self, path: str, content: str, create_directories: bool = True) -> ToolResult:
        target = resolve_inside(self.root, path)
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        if create_directories:
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult.success_result(unified_diff(old, content, target), {"path": str(target)})


class EditTool(Tool):
    """基于精确字符串替换的编辑工具。"""
    name = "edit_file"
    description = "Replace exact text in a file inside the working directory."
    kind = ToolKind.WRITE

    def __init__(self, root: Path) -> None:
        self.root = root

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean", "default": False},
                },
                "required": ["path", "old_string", "new_string"],
            },
        }

    async def execute(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult:
        """执行精确替换；多处匹配时默认拒绝，防止误改。"""
        target = resolve_inside(self.root, path)
        old = target.read_text(encoding="utf-8")
        count = old.count(old_string)
        if count == 0:
            return ToolResult.error_result("old_string was not found.")
        if count > 1 and not replace_all:
            return ToolResult.error_result("old_string occurs multiple times. Set replace_all=true.")
        new = old.replace(old_string, new_string) if replace_all else old.replace(old_string, new_string, 1)
        target.write_text(new, encoding="utf-8")
        return ToolResult.success_result(unified_diff(old, new, target), {"path": str(target), "replacements": count})


class ListDirectoryTool(Tool):
    """列出目录条目，目录名用斜杠结尾。"""
    name = "list_dir"
    description = "List files and directories inside the working directory."
    kind = ToolKind.READ

    def __init__(self, root: Path) -> None:
        self.root = root

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "include_hidden": {"type": "boolean", "default": False},
                },
            },
        }

    async def execute(self, path: str = ".", include_hidden: bool = False) -> ToolResult:
        target = resolve_inside(self.root, path)
        rows = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if not include_hidden and child.name.startswith("."):
                continue
            rows.append(child.name + ("/" if child.is_dir() else ""))
        return ToolResult.success_result("\n".join(rows), {"count": len(rows)})


class GlobTool(Tool):
    """在工作目录内按 glob 模式查找文件。"""
    name = "glob"
    description = "Find files by glob pattern inside the working directory."
    kind = ToolKind.READ

    def __init__(self, root: Path) -> None:
        self.root = root

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "search_path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
        }

    async def execute(self, pattern: str, search_path: str = ".") -> ToolResult:
        base = resolve_inside(self.root, search_path)
        matches = [p for p in base.glob(pattern) if p.is_file()]
        shown = matches[:500]
        rel = [str(p.relative_to(self.root)) for p in shown]
        suffix = "\n[truncated]" if len(matches) > len(shown) else ""
        return ToolResult.success_result("\n".join(rel) + suffix, {"count": len(matches)})


def register_file_tools(registry: Any, cwd: Path) -> None:
    """把所有内置文件工具注册到工具表。"""
    for tool in [ReadFileTool(cwd), WriteFileTool(cwd), EditTool(cwd), ListDirectoryTool(cwd), GlobTool(cwd)]:
        registry.register(tool)
