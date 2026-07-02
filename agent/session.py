"""Agent 会话装配模块。

负责把配置、LLM、上下文、工具、审批、持久化、Hooks、循环检测、MCP 和
子代理组装成一个 Session。其它模块不需要知道初始化顺序。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .approval import ApprovalManager
from .config import load_config
from .context import ContextManager, build_system_prompt
from .discovery import discover_and_register
from .file_tools import register_file_tools
from .hooks import HookSystem, build_hook_system
from .llm_client import LLMClient
from .loop_detection import LoopDetector
from .mcp import MCPManager
from .network_tools import register_network_tools
from .persistence import PersistenceManager
from .sub_agents import BaseSubAgent, build_sub_agents
from .tooling import ToolRegistry


@dataclass(slots=True)
class Session:
    """完整 Agent 运行时状态。"""

    session_id: str
    created_at: datetime
    updated_at: datetime
    turn_count: int
    llm: LLMClient
    ctx: ContextManager
    registry: ToolRegistry
    approval_mgr: ApprovalManager
    persistence: PersistenceManager
    hook_system: HookSystem
    loop_detector: LoopDetector
    sub_agents: dict[str, BaseSubAgent]
    config: dict[str, Any]
    cwd: Path
    mcp_manager: MCPManager | None = None
    discovered_tools: list[Any] = field(default_factory=list)

    def increment_turn(self) -> None:
        """记录一次用户任务轮次。"""
        self.turn_count += 1
        self.updated_at = datetime.now(timezone.utc)


async def create_agent(
    model: str = "gpt-oss:120b",
    cwd: Path = Path("."),
    approval_policy: str = "on_request",
    enable_mcp: bool = False,
    enable_discovery: bool = True,
) -> Session:
    """按课程第 15 章的顺序组装完整 Agent。"""
    cwd = cwd.resolve()
    config = load_config(cwd, {"model": model, "approval_policy": approval_policy})

    llm = LLMClient(
        model=config["model"],
        base_url=config.get("base_url", "http://localhost:11434/v1"),
        api_key=config.get("api_key", "ollama"),
    )
    ctx = ContextManager(
        system_prompt=build_system_prompt(str(cwd)),
        context_window=int(config.get("context_window", 128_000)),
    )
    registry = ToolRegistry()
    register_file_tools(registry, cwd)
    register_network_tools(registry)

    discovered_tools = []
    if enable_discovery:
        discovered_tools = await discover_and_register(registry, cwd)

    approval_mgr = ApprovalManager(policy=config.get("approval_policy", approval_policy), cwd=cwd)
    persistence = PersistenceManager(cwd / ".ai_agent")
    hook_system = build_hook_system(config.get("hooks", []), cwd)
    loop_detector = LoopDetector(
        max_exact_repeats=int(config.get("max_exact_repeats", 3)),
        max_cycle_length=int(config.get("max_cycle_length", 4)),
    )
    mcp_manager = None
    if enable_mcp:
        mcp_manager = MCPManager(config.get("mcp_servers", {}))
        await mcp_manager.connect_all()

    return Session(
        session_id=uuid.uuid4().hex[:12],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        turn_count=0,
        llm=llm,
        ctx=ctx,
        registry=registry,
        approval_mgr=approval_mgr,
        persistence=persistence,
        hook_system=hook_system,
        loop_detector=loop_detector,
        mcp_manager=mcp_manager,
        sub_agents=build_sub_agents(llm, registry),
        config=config,
        cwd=cwd,
        discovered_tools=discovered_tools,
    )
