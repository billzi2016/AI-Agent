"""循环检测模块。

记录工具调用签名，检测重复调用和短周期循环，防止 Agent 卡在同一动作上。
检测到循环后返回建议文本，由 Agent loop 写回上下文提醒模型换策略。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LoopDetectionResult:
    """循环检测结果。"""

    description: str
    suggestion: str


class LoopDetector:
    """基于工具名和参数 hash 的轻量循环检测器。"""

    def __init__(self, max_exact_repeats: int = 3, max_cycle_length: int = 4) -> None:
        self.max_exact_repeats = max_exact_repeats
        self.max_cycle_length = max_cycle_length
        self.history: list[str] = []

    def record(self, tool_name: str, params: dict[str, Any]) -> None:
        """记录一次工具调用签名。"""
        payload = json.dumps({"tool": tool_name, "params": params}, sort_keys=True, ensure_ascii=False)
        self.history.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())

    def check(self) -> LoopDetectionResult | None:
        """检查精确重复和短周期循环。"""
        if len(self.history) >= self.max_exact_repeats:
            tail = self.history[-self.max_exact_repeats :]
            if len(set(tail)) == 1:
                return LoopDetectionResult("Same tool call repeated too many times.", "Change strategy or inspect a different signal.")

        # 检查最近序列是否由同一个短模式重复两次。
        for size in range(2, self.max_cycle_length + 1):
            if len(self.history) >= size * 2 and self.history[-size:] == self.history[-2 * size : -size]:
                return LoopDetectionResult("Repeated tool-call cycle detected.", "Summarize what is known and choose a new action.")
        return None
