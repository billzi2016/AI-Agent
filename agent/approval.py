"""审批与安全策略模块。

根据工具是否会修改状态、当前审批策略和路径安全性决定是否允许执行工具。
这里保持策略集中，避免在 Agent loop 里散落大量 if-else。
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any


class ApprovalPolicy(str, Enum):
    """支持的审批策略。"""

    ON_REQUEST = "on_request"
    AUTO = "auto"
    AUTO_EDIT = "autoEdit"
    NEVER = "never"
    YOLO = "YOLO"


class ApprovalManager:
    """统一处理工具调用审批。"""

    def __init__(self, policy: str = "on_request", cwd: Path | None = None) -> None:
        self.policy = policy
        self.cwd = cwd.resolve() if cwd else None

    async def request_approval(self, tool_name: str, params: dict[str, Any], mutating: bool = False) -> bool:
        """根据策略返回是否允许执行工具。"""
        if self.policy == ApprovalPolicy.NEVER.value and mutating:
            return False
        if self.policy == ApprovalPolicy.YOLO.value:
            return True
        if self.policy == ApprovalPolicy.AUTO.value and not self._looks_dangerous(tool_name, params):
            return True
        if self.policy == ApprovalPolicy.AUTO_EDIT.value and tool_name in {"write_file", "edit_file"}:
            return self._path_is_safe(params.get("path"))
        if not mutating:
            return True

        # 课程版 CLI 不做真正交互弹窗，这里用终端确认保持最小闭环。
        answer = input(f"Allow tool call {tool_name} with params {params}? [y/N] ").strip().lower()
        return answer in {"y", "yes"}

    def _path_is_safe(self, path: Any) -> bool:
        """检查路径是否留在工作目录内。"""
        if not self.cwd or not isinstance(path, str):
            return False
        target = (self.cwd / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        return target == self.cwd or self.cwd in target.parents

    def _looks_dangerous(self, tool_name: str, params: dict[str, Any]) -> bool:
        """判断工具调用是否明显有风险。"""
        if tool_name in {"write_file", "edit_file"}:
            return not self._path_is_safe(params.get("path"))
        if tool_name == "shell":
            command = str(params.get("command", ""))
            return any(token in command for token in ["rm ", "sudo", "chmod", "chown", "git reset"])
        return False
