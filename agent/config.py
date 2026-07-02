"""配置加载模块。

负责读取 `.ai_agent/config.toml`，并把配置文件、默认值和 CLI 参数合并成
一份运行时配置。这个模块只处理配置，不创建 Agent 对象，避免职责混杂。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "model": "gpt-oss:120b",
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
    "approval_policy": "on_request",
    "context_window": 128_000,
    "max_exact_repeats": 3,
    "max_cycle_length": 4,
    "hooks": [],
    "mcp_servers": {},
}


def load_config(cwd: Path, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """加载配置，并按“默认值 < 配置文件 < CLI 覆盖”的优先级合并。"""
    config = dict(DEFAULT_CONFIG)
    config_path = cwd / ".ai_agent" / "config.toml"
    if config_path.exists():
        try:
            try:
                import tomllib
            except ImportError:  # pragma: no cover - Python < 3.11 fallback
                import tomli as tomllib  # type: ignore

            with config_path.open("rb") as fh:
                config.update(tomllib.load(fh))
        except Exception as exc:
            print(f"[warning] Failed to load config {config_path}: {exc}. Using defaults.")

    if overrides:
        config.update({k: v for k, v in overrides.items() if v is not None})
    return config
