"""测试工具系统和文件工具。

覆盖 ToolRegistry 的统一调用，以及文件工具最关键的工作目录边界检查。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent.file_tools import EditTool, ReadFileTool, WriteFileTool, resolve_inside
from agent.tooling import ToolRegistry


class ToolTests(unittest.IsolatedAsyncioTestCase):
    """工具注册和文件工具测试。"""

    async def test_registry_invokes_registered_tool(self) -> None:
        """注册表应能按名称调用工具并返回 ToolResult。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("hello\n", encoding="utf-8")
            registry = ToolRegistry()
            registry.register(ReadFileTool(root))

            result = await registry.invoke("read_file", {"path": "note.txt"})
            self.assertTrue(result.success)
            self.assertIn("hello", result.content)

    async def test_write_and_edit_file_return_diff(self) -> None:
        """写入和编辑工具应修改文件并返回 diff。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write = WriteFileTool(root)
            edit = EditTool(root)

            write_result = await write.execute("a/b.txt", "old text")
            edit_result = await edit.execute("a/b.txt", "old", "new")

            self.assertTrue(write_result.success)
            self.assertTrue(edit_result.success)
            self.assertEqual((root / "a" / "b.txt").read_text(encoding="utf-8"), "new text")
            self.assertIn("-old text", edit_result.content)
            self.assertIn("+new text", edit_result.content)

    def test_resolve_inside_rejects_escape(self) -> None:
        """路径解析必须拒绝逃出工作目录的路径。"""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                resolve_inside(Path(tmp), "../outside.txt")


if __name__ == "__main__":
    unittest.main()
