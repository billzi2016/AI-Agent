"""测试运行时辅助模块。

这里覆盖循环检测、持久化、Hook 构建和 slash command 等不依赖真实模型的逻辑。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.approval import ApprovalManager
from agent.cli import handle_slash_command
from agent.context import ContextManager
from agent.hooks import HookTrigger, build_hook_system
from agent.loop_detection import LoopDetector
from agent.persistence import PersistenceManager


class RuntimeModuleTests(unittest.TestCase):
    """运行时模块测试。"""

    def test_loop_detector_catches_repeated_action(self) -> None:
        """同一个工具调用重复多次时应被检测到。"""
        detector = LoopDetector(max_exact_repeats=3)
        for _ in range(3):
            detector.record("read_file", {"path": "a.py"})
        result = detector.check()
        self.assertIsNotNone(result)
        self.assertIn("repeated", result.description.lower())

    def test_persistence_round_trip(self) -> None:
        """Session 保存后应能恢复 messages 和 token 统计。"""
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ContextManager("system")
            ctx.add_user_message("hello")
            ctx.update_usage(7, 3)
            manager = PersistenceManager(Path(tmp))
            sid = manager.save_session(ctx, "sid")

            restored = ContextManager("system")
            manager.load_session(sid, restored)

            self.assertEqual(restored.messages, ctx.messages)
            self.assertEqual(restored.prompt_tokens, 7)
            self.assertEqual(restored.completion_tokens, 3)

    def test_hook_system_skips_invalid_items(self) -> None:
        """非法 Hook 配置应被跳过，而不是让 Agent 初始化失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            system = build_hook_system(
                [
                    {"trigger": "before_agent", "command": "echo ok"},
                    {"trigger": "missing"},
                ],
                Path(tmp),
            )
        self.assertEqual(len(system.hooks), 1)
        self.assertEqual(system.hooks[0].trigger, HookTrigger.BEFORE_AGENT)

    def test_approval_auto_edit_checks_path(self) -> None:
        """autoEdit 策略应允许工作目录内路径、拒绝越界路径。"""
        with tempfile.TemporaryDirectory() as tmp:
            manager = ApprovalManager("autoEdit", Path(tmp))
            self.assertTrue(manager._path_is_safe("inside.txt"))
            self.assertFalse(manager._path_is_safe("../outside.txt"))

    def test_slash_clear_command_clears_context(self) -> None:
        """`/clear` 命令应清空上下文但保留 system prompt。"""
        class FakeSession:
            pass

        session = FakeSession()
        session.ctx = ContextManager("system")
        session.ctx.add_user_message("hello")

        with patch("builtins.print"):
            handled = handle_slash_command("/clear", session)

        self.assertTrue(handled)
        self.assertEqual(len(session.ctx.messages), 1)


if __name__ == "__main__":
    unittest.main()
