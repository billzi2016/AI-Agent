"""子代理模块。

提供只读代码库调查和代码审查两个示例子代理。子代理共享 LLM，但只拿到
有限工具集合的注册表，避免主代理把全部能力无差别暴露给辅助任务。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SubAgentParameters:
    """子代理调用参数。"""

    action: str
    content: str
    max_turns: int = 6
    timeout: float = 120.0


class BaseSubAgent:
    """子代理基类，负责统一 prompt 包装。"""

    name = "base"
    role = "General helper"

    def __init__(self, llm: Any, registry: Any) -> None:
        self.llm = llm
        self.registry = registry

    async def run(self, params: SubAgentParameters) -> str:
        """执行一次子代理任务。"""
        prompt = f"You are {self.role}.\nAction: {params.action}\nTask:\n{params.content}"
        coro = self.llm.chat_completion(messages=[{"role": "user", "content": prompt}], tools=self.registry.get_schemas())
        response, _ = await asyncio.wait_for(coro, timeout=params.timeout)
        return response if isinstance(response, str) else str(response)


class CodebaseInvestigator(BaseSubAgent):
    """只读代码库调查子代理。"""

    name = "investigator"
    role = "a codebase investigator that maps structure and gathers facts before implementation"


class CodeReviewer(BaseSubAgent):
    """代码审查子代理。"""

    name = "reviewer"
    role = "a strict code reviewer focused on bugs, regressions, and missing tests"


def build_sub_agents(llm: Any, registry: Any) -> dict[str, BaseSubAgent]:
    """构建默认子代理集合。"""
    return {
        "investigator": CodebaseInvestigator(llm, registry),
        "reviewer": CodeReviewer(llm, registry),
    }
