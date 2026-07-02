"""测试配置加载和上下文管理。

这些测试不依赖真实模型，用来保证默认配置、CLI 覆盖、消息维护和 token
统计这些基础能力稳定可用。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent.config import load_config
from agent.context import ContextManager, build_system_prompt


class ConfigAndContextTests(unittest.TestCase):
    """配置和上下文模块的单元测试。"""

    def test_load_config_uses_defaults_and_overrides(self) -> None:
        """没有配置文件时，应返回默认值并应用覆盖参数。"""
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(Path(tmp), {"model": "custom-model"})
        self.assertEqual(config["model"], "custom-model")
        self.assertEqual(config["base_url"], "http://localhost:11434/v1")

    def test_context_keeps_system_prompt_after_clear(self) -> None:
        """清空上下文后，system prompt 不能丢。"""
        ctx = ContextManager(build_system_prompt("/tmp/work"))
        ctx.add_user_message("hello")
        ctx.add_assistant_message("world")
        self.assertEqual(len(ctx.get_messages()), 3)

        ctx.clear_messages()
        messages = ctx.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "system")

    def test_context_stats_include_usage(self) -> None:
        """模型返回的 token 用量应进入 stats。"""
        ctx = ContextManager("system")
        ctx.update_usage(10, 5)
        stats = ctx.stats()
        self.assertEqual(stats["prompt_tokens"], 10)
        self.assertEqual(stats["completion_tokens"], 5)


if __name__ == "__main__":
    unittest.main()
