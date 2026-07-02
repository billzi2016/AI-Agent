"""命令行入口模块。

提供 Click CLI、交互式 REPL、slash commands 和一次性 prompt 模式。
这里只负责用户交互，Agent 初始化和执行分别交给 session/loop 模块。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from .loop import agentic_loop
from .session import Session, create_agent


def handle_slash_command(command_text: str, session: Session) -> bool:
    """处理交互模式中的 `/` 命令；返回 True 表示命令已处理。"""
    parts = command_text.strip().split(None, 1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command == "/help":
        print(
            """
Available commands:
  /help                  Show this help
  /exit                  Exit the agent
  /clear                 Clear conversation history
  /config                Show current config
  /model <name>          Switch model
  /approval <policy>     Switch approval policy
  /stats                 Show token stats
  /sessions              List saved sessions
  /save                  Save current session
  /resume <id>           Resume a saved session
  /tools                 List registered tools
  /mcp                   List MCP server status
  /checkpoint            Create a checkpoint
  /restore <id>          Restore a checkpoint
"""
        )
        return True

    if command == "/exit":
        raise SystemExit(0)

    if command == "/clear":
        session.ctx.clear_messages()
        print("Conversation history cleared.")
        return True

    if command == "/config":
        for key, value in session.config.items():
            print(f"{key}: {value}")
        return True

    if command == "/model":
        if not arg:
            print("Usage: /model <model_name>")
        else:
            session.llm.model = arg
            session.config["model"] = arg
            print(f"Model switched to: {arg}")
        return True

    if command == "/approval":
        valid = {"on_request", "auto", "autoEdit", "never", "YOLO"}
        if arg not in valid:
            print(f"Invalid policy. Options: {', '.join(sorted(valid))}")
        else:
            session.approval_mgr.policy = arg
            session.config["approval_policy"] = arg
            print(f"Approval policy switched to: {arg}")
        return True

    if command == "/stats":
        for key, value in session.ctx.stats().items():
            print(f"{key}: {value}")
        return True

    if command == "/sessions":
        sessions = session.persistence.list_sessions()
        print("\n".join(sessions) if sessions else "No saved sessions.")
        return True

    if command == "/save":
        sid = session.persistence.save_session(session.ctx, session.session_id)
        print(f"Session saved: {sid}")
        return True

    if command == "/resume":
        if not arg:
            print("Usage: /resume <session_id>")
        else:
            session.persistence.load_session(arg, session.ctx)
            print(f"Session resumed: {arg}")
        return True

    if command == "/tools":
        tools = session.registry.list_tools()
        print(f"Registered tools: {len(tools)}")
        for tool in tools:
            print(f"  {tool.name:20s} [{tool.kind.value}] {tool.description}")
        return True

    if command == "/mcp":
        if not session.mcp_manager:
            print("MCP is disabled.")
        else:
            print("\n".join(session.mcp_manager.list_tools()))
        return True

    if command == "/checkpoint":
        cid = session.persistence.create_checkpoint(session.ctx, session.session_id)
        print(f"Checkpoint created: {cid}")
        return True

    if command == "/restore":
        if not arg:
            print("Usage: /restore <checkpoint_id>")
        else:
            session.persistence.restore_checkpoint(arg, session.ctx)
            print(f"Checkpoint restored: {arg}")
        return True

    return False


async def interactive_loop(session: Session, max_turns: int) -> None:
    """运行交互式 REPL。"""
    print("\nAI Coding Agent is ready. Type /help for commands, /exit to quit.")
    while True:
        try:
            user_input = input("\nyou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not user_input:
            continue
        if user_input.startswith("/"):
            if not handle_slash_command(user_input, session):
                print(f"Unknown command: {user_input}. Type /help.")
            continue
        result = await agentic_loop(session, user_input, max_turns=max_turns, verbose=True)
        print(
            f"\n[stats] turns={result['turns']} tools={result['tools_called']} "
            f"elapsed={result['elapsed_sec']}s compressed={result['compressed']}"
        )


async def run(
    prompt: str | None,
    model: str,
    cwd: Path,
    max_turns: int,
    approval: str,
    enable_mcp: bool,
    enable_discovery: bool,
) -> None:
    """初始化 Agent，并根据是否传入 prompt 决定一次性运行或进入 REPL。"""
    print(f"[init] model={model} cwd={cwd} approval={approval}")
    session = await create_agent(
        model=model,
        cwd=cwd,
        approval_policy=approval,
        enable_mcp=enable_mcp,
        enable_discovery=enable_discovery,
    )
    try:
        if prompt:
            result = await agentic_loop(session, prompt, max_turns=max_turns, verbose=True)
            print("\n[done]")
            print(f"  turns:       {result['turns']}")
            print(f"  tools:       {result['tools_called']}")
            print(f"  elapsed:     {result['elapsed_sec']}s")
            print(f"  compressed:  {result['compressed']}")
            print(f"  tokens:      {result.get('token_usage', {})}")
        else:
            await interactive_loop(session, max_turns)
    finally:
        if session.mcp_manager:
            await session.mcp_manager.disconnect_all()
        await session.llm.close()


@click.command()
@click.option("--prompt", "-p", default=None, help="Run one task and exit.")
@click.option("--model", "-m", default="gpt-oss:120b", help="LLM model name.")
@click.option("--cwd", default=".", type=click.Path(), help="Working directory.")
@click.option("--max-turns", default=20, help="Maximum agent turns.")
@click.option(
    "--approval",
    default="on_request",
    type=click.Choice(["on_request", "auto", "autoEdit", "never", "YOLO"]),
    help="Approval policy.",
)
@click.option("--no-mcp", is_flag=True, help="Disable MCP integration.")
@click.option("--no-discovery", is_flag=True, help="Disable custom tool discovery.")
def main(prompt: str | None, model: str, cwd: str, max_turns: int, approval: str, no_mcp: bool, no_discovery: bool) -> None:
    """AI Coding Agent command-line entry point."""
    asyncio.run(
        run(
            prompt=prompt,
            model=model,
            cwd=Path(cwd),
            max_turns=max_turns,
            approval=approval,
            enable_mcp=not no_mcp,
            enable_discovery=not no_discovery,
        )
    )
