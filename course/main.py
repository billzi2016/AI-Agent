"""
course/main.py — AI Coding Agent 主入口

用法示例：
    python main.py
    python main.py -p "分析 src/ 目录，列出所有函数名"
    python main.py -m gpt-oss:120b --approval auto
"""

import asyncio
import sys
import os
from pathlib import Path

# 把 course/ 的父目录加入搜索路径，确保能导入 src/
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import click
except ImportError:
    print("缺少依赖：pip install click")
    sys.exit(1)


# ── 初始化流程 ─────────────────────────────────────────────────────

async def create_agent(
    model: str = "gpt-oss:120b",
    cwd: Path = Path("."),
    approval_policy: str = "on_request",
    enable_mcp: bool = False,
    enable_discovery: bool = True,
):
    """
    完整初始化流程：按顺序装配所有模块，返回 Session。

    步骤：
      1. 加载配置（.ai_agent/config.toml，不存在用默认值）
      2. 创建 Session，初始化 LLMClient + ContextManager
      3. 注册文件工具 + 网络工具
      4. 如果 enable_discovery：运行 ToolDiscovery
      5. 注册子代理（CodebaseInvestigator + CodeReviewer）
      6. 初始化 ApprovalManager
      7. 初始化 PersistenceManager
      8. 初始化 HookSystem（从配置读取）
      9. 初始化 LoopDetector
     10. 如果 enable_mcp：初始化 MCPManager
    """
    from src.llm_client import LLMClient
    from src.context_manager import ContextManager, build_system_prompt
    from src.tool_framework import ToolRegistry

    # ── 1. 加载配置 ─────────────────────────────────────────────────
    config = _load_config(cwd)
    config.setdefault("model", model)
    config.setdefault("approval_policy", approval_policy)

    # ── 2. 创建核心对象 ──────────────────────────────────────────────
    llm = LLMClient(
        model=config.get("model", model),
        base_url=config.get("base_url", "http://localhost:11434/v1"),
        api_key=config.get("api_key", "ollama"),
    )
    system_prompt = build_system_prompt(working_directory=str(cwd))
    ctx = ContextManager(system_prompt=system_prompt)
    registry = ToolRegistry()

    # ── 3. 注册工具 ──────────────────────────────────────────────────
    _register_file_tools(registry, cwd)
    _register_network_tools(registry)

    # ── 4. Tool Discovery ────────────────────────────────────────────
    discovered_tools = []
    if enable_discovery:
        discovered_tools = await _run_discovery(registry, cwd)

    # ── 5. 子代理 ────────────────────────────────────────────────────
    sub_agents = _build_sub_agents(llm, registry)

    # ── 6. ApprovalManager ───────────────────────────────────────────
    approval_mgr = _build_approval_manager(config.get("approval_policy", approval_policy))

    # ── 7. PersistenceManager ────────────────────────────────────────
    persistence = _build_persistence(cwd)

    # ── 8. HookSystem ────────────────────────────────────────────────
    hook_system = _build_hook_system(config.get("hooks", []))

    # ── 9. LoopDetector ──────────────────────────────────────────────
    from src.hooks_and_loop_detection import LoopDetector
    loop_detector = LoopDetector(
        max_exact_repeats=config.get("max_exact_repeats", 3),
        max_cycle_length=config.get("max_cycle_length", 4),
    )

    # ── 10. MCPManager（可选）────────────────────────────────────────
    mcp_manager = None
    if enable_mcp:
        mcp_manager = await _build_mcp_manager(config.get("mcp_servers", {}))

    # ── 组装 Session ─────────────────────────────────────────────────
    session = {
        "llm": llm,
        "ctx": ctx,
        "registry": registry,
        "approval_mgr": approval_mgr,
        "persistence": persistence,
        "hook_system": hook_system,
        "loop_detector": loop_detector,
        "mcp_manager": mcp_manager,
        "sub_agents": sub_agents,
        "config": config,
        "cwd": cwd,
        "discovered_tools": discovered_tools,
    }
    return session


def _load_config(cwd: Path) -> dict:
    """加载 .ai_agent/config.toml，不存在则返回空字典。"""
    config_path = cwd / ".ai_agent" / "config.toml"
    if not config_path.exists():
        return {}
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"[警告] 配置文件加载失败：{e}，使用默认配置")
        return {}


def _register_file_tools(registry, cwd: Path):
    """注册所有文件工具。"""
    try:
        from src.file_tools import (
            ReadFileTool, WriteFileTool, EditTool,
            ListDirectoryTool, GlobTool,
        )
        for tool_cls in [ReadFileTool, WriteFileTool, EditTool,
                         ListDirectoryTool, GlobTool]:
            registry.register(tool_cls(cwd))
    except ImportError as e:
        print(f"[警告] 文件工具加载失败：{e}")


def _register_network_tools(registry):
    """注册网络工具。"""
    try:
        from src.network_tools import WebSearchTool, WebFetchTool
        registry.register(WebSearchTool())
        registry.register(WebFetchTool())
    except ImportError as e:
        print(f"[警告] 网络工具加载失败：{e}")


async def _run_discovery(registry, cwd: Path) -> list:
    """运行 ToolDiscovery，发现并注册额外工具。"""
    try:
        from src.tool_discovery import ToolDiscovery
        discovery = ToolDiscovery(cwd=cwd)
        tools = await discovery.discover()
        for tool in tools:
            registry.register(tool)
        return tools
    except (ImportError, Exception) as e:
        print(f"[信息] ToolDiscovery 不可用：{e}")
        return []


def _build_sub_agents(llm, registry) -> dict:
    """构建子代理。"""
    agents = {}
    try:
        from src.sub_agents import CodebaseInvestigator, CodeReviewer
        agents["investigator"] = CodebaseInvestigator(llm=llm, registry=registry)
        agents["reviewer"] = CodeReviewer(llm=llm, registry=registry)
    except (ImportError, Exception) as e:
        print(f"[信息] 子代理不可用：{e}")
    return agents


def _build_approval_manager(policy: str):
    """构建 ApprovalManager。"""
    try:
        from src.approval_and_safety import ApprovalManager
        return ApprovalManager(policy=policy)
    except (ImportError, Exception) as e:
        print(f"[信息] ApprovalManager 不可用：{e}")
        return None


def _build_persistence(cwd: Path):
    """构建 PersistenceManager。"""
    try:
        from src.persistence_and_checkpoint import PersistenceManager
        store_dir = cwd / ".ai_agent" / "sessions"
        store_dir.mkdir(parents=True, exist_ok=True)
        return PersistenceManager(store_dir=store_dir)
    except (ImportError, Exception) as e:
        print(f"[信息] PersistenceManager 不可用：{e}")
        return None


def _build_hook_system(hooks_config: list):
    """从配置列表构建 HookSystem。"""
    try:
        from src.hooks_and_loop_detection import HookSystem, HookConfig, HookTrigger
        configs = []
        for item in hooks_config:
            try:
                configs.append(HookConfig(
                    trigger=HookTrigger(item["trigger"]),
                    command=item["command"],
                    timeout=float(item.get("timeout", 10.0)),
                    enabled=bool(item.get("enabled", True)),
                ))
            except (KeyError, ValueError):
                pass
        return HookSystem(configs)
    except (ImportError, Exception) as e:
        print(f"[信息] HookSystem 不可用：{e}")
        return None


async def _build_mcp_manager(servers_config: dict):
    """构建 MCPManager（可选）。"""
    try:
        from src.mcp_protocol import MCPManager
        mgr = MCPManager(servers=servers_config)
        await mgr.connect_all()
        return mgr
    except (ImportError, Exception) as e:
        print(f"[信息] MCPManager 不可用：{e}")
        return None


# ── 完整 Agentic Loop ──────────────────────────────────────────────

async def agentic_loop(
    session: dict,
    user_message: str,
    max_turns: int = 20,
    verbose: bool = True,
) -> dict:
    """
    完整 agentic loop，整合所有中间件：
    - 上下文压缩（第 08 章）
    - 审批管理（第 09 章）
    - Hooks（第 14 章）
    - 循环检测（第 14 章）
    """
    import json
    import time

    llm          = session["llm"]
    ctx          = session["ctx"]
    registry     = session["registry"]
    approval_mgr = session.get("approval_mgr")
    hook_system  = session.get("hook_system")
    loop_det     = session.get("loop_detector")

    # 导入压缩函数
    compress_fn = None
    try:
        from src.context_compression import compress_if_needed
        compress_fn = compress_if_needed
    except ImportError:
        pass

    # 导入 HookTrigger
    HookTrigger = None
    try:
        from src.hooks_and_loop_detection import HookTrigger as _HT
        HookTrigger = _HT
    except ImportError:
        pass

    start_time = time.time()
    tools_called: list[str] = []
    turn = 0
    compressed = False

    # ── BEFORE_AGENT hook ──────────────────────────────────────────
    if hook_system and HookTrigger:
        await hook_system.trigger(HookTrigger.BEFORE_AGENT)

    ctx.add_user_message(user_message)

    if verbose:
        print(f"\n[Agent] 用户: {user_message}")
        print(f"[Agent] 工具数量: {len(registry.list_tools())}")

    final_response = ""

    for turn in range(max_turns):
        # ── 每轮开始前检查是否需要压缩 ─────────────────────────────
        if compress_fn and ctx.needs_compression():
            if verbose:
                print(f"[Agent] 触发上下文压缩（第 {turn+1} 轮）")
            await compress_fn(ctx, llm)
            compressed = True

        # ── 调用 LLM ────────────────────────────────────────────────
        try:
            tools_schema = registry.get_schemas() if registry.list_tools() else None
            response_text, usage = await llm.chat_completion(
                messages=ctx.get_messages(),
                tools=tools_schema,
            )
            ctx.update_usage(usage.prompt_tokens, usage.completion_tokens)
        except Exception as e:
            if verbose:
                print(f"[Agent] LLM 调用失败：{e}")
            # ── ON_ERROR hook ────────────────────────────────────────
            if hook_system and HookTrigger:
                await hook_system.trigger(
                    HookTrigger.ON_ERROR,
                    context={"error": str(e)}
                )
            break

        # ── 解析 LLM 响应 ────────────────────────────────────────────
        # 如果响应是字符串且不含工具调用，视为最终回答
        if isinstance(response_text, str):
            ctx.add_assistant_message(response_text)
            final_response = response_text
            if verbose:
                print(f"\n[Agent] 最终回答:\n{response_text}")
            break

        # 处理工具调用（response_text 为 dict，含 tool_calls）
        if isinstance(response_text, dict) and "tool_calls" in response_text:
            content = response_text.get("content", "")
            tool_calls = response_text["tool_calls"]
            ctx.add_assistant_message(content, tool_calls=tool_calls)

            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name", "")
                raw_args  = tc.get("function", {}).get("arguments", "{}")
                tool_id   = tc.get("id", "")

                try:
                    params = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    params = {}

                if verbose:
                    print(f"[Agent] 工具调用: {tool_name}({json.dumps(params, ensure_ascii=False)[:80]})")

                # ── ApprovalManager ──────────────────────────────────
                if approval_mgr:
                    try:
                        approved = await approval_mgr.request_approval(
                            tool_name=tool_name, params=params
                        )
                        if not approved:
                            ctx.add_tool_result(tool_id, "用户拒绝了此操作")
                            continue
                    except Exception:
                        pass  # approval 模块不可用时忽略

                # ── BEFORE_TOOL hook ─────────────────────────────────
                if hook_system and HookTrigger:
                    await hook_system.trigger(
                        HookTrigger.BEFORE_TOOL,
                        context={"tool_name": tool_name}
                    )

                # ── 循环检测 ─────────────────────────────────────────
                if loop_det:
                    loop_det.record(tool_name, params)
                    loop_result = loop_det.check()
                    if loop_result:
                        msg = (
                            f"[循环检测] {loop_result.description}\n"
                            f"建议：{loop_result.suggestion}"
                        )
                        if verbose:
                            print(f"[Agent] {msg}")
                        ctx.add_tool_result(tool_id, msg)
                        continue

                # ── 执行工具 ─────────────────────────────────────────
                tool_result = await registry.invoke(tool_name, params)
                tools_called.append(tool_name)
                success = tool_result.success

                if verbose:
                    status = "成功" if success else "失败"
                    preview = tool_result.content[:120].replace("\n", " ")
                    print(f"[Agent]   -> [{status}] {preview}")

                ctx.add_tool_result(tool_id, tool_result.content)

                # ── AFTER_TOOL hook ──────────────────────────────────
                if hook_system and HookTrigger:
                    await hook_system.trigger(
                        HookTrigger.AFTER_TOOL,
                        context={
                            "tool_name": tool_name,
                            "tool_success": str(success).lower(),
                        }
                    )
        else:
            # 未知响应格式，当作最终回答
            final_response = str(response_text)
            break

    # ── AFTER_AGENT hook ────────────────────────────────────────────
    if hook_system and HookTrigger:
        await hook_system.trigger(HookTrigger.AFTER_AGENT)

    elapsed = time.time() - start_time
    stats = ctx.stats()

    return {
        "response": final_response,
        "turns": turn + 1,
        "tools_called": tools_called,
        "elapsed_sec": round(elapsed, 2),
        "compressed": compressed,
        "token_usage": stats,
    }


# ── CLI ───────────────────────────────────────────────────────────

def handle_slash_command(cmd: str, session: dict) -> bool:
    """
    处理 / 命令。返回 True 表示命令已处理，返回 False 表示未识别。

    支持的命令：
      /help                  显示帮助
      /exit                  退出
      /clear                 清空对话历史
      /config                显示当前配置
      /model <name>          切换模型
      /approval <policy>     切换审批策略
      /stats                 显示 token 统计
      /sessions              列出已保存的 Session
      /save                  保存当前 Session
      /resume <id>           恢复指定 Session
      /tools                 列出已注册工具
      /mcp                   列出 MCP 工具（如已启用）
      /checkpoint            创建检查点
      /restore <id>          恢复到指定检查点
    """
    parts = cmd.strip().split(None, 1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    ctx        = session.get("ctx")
    registry   = session.get("registry")
    persistence = session.get("persistence")
    mcp_manager = session.get("mcp_manager")
    config     = session.get("config", {})

    if command == "/help":
        print("""
可用命令：
  /help                  显示此帮助
  /exit                  退出 Agent
  /clear                 清空对话历史
  /config                显示当前配置
  /model <name>          切换模型（如 /model llama3:8b）
  /approval <policy>     切换审批策略（on_request/auto/autoEdit/never/YOLO）
  /stats                 显示 token 统计
  /sessions              列出已保存的 Session
  /save                  保存当前 Session
  /resume <id>           恢复指定 Session（如 /resume abc123）
  /tools                 列出已注册工具
  /mcp                   列出 MCP 工具（如已启用）
  /checkpoint            创建检查点
  /restore <id>          恢复到指定检查点
""")
        return True

    elif command == "/exit":
        print("退出 Agent。")
        sys.exit(0)

    elif command == "/clear":
        if ctx:
            ctx.clear_messages()
            print("对话历史已清空。")
        return True

    elif command == "/config":
        print("当前配置：")
        for k, v in config.items():
            print(f"  {k}: {v}")
        return True

    elif command == "/model":
        if not arg:
            print("用法：/model <model_name>")
        else:
            if session.get("llm"):
                session["llm"].model = arg
                config["model"] = arg
                print(f"模型已切换为：{arg}")
        return True

    elif command == "/approval":
        valid = {"on_request", "auto", "autoEdit", "never", "YOLO"}
        if arg not in valid:
            print(f"无效策略，可选：{', '.join(sorted(valid))}")
        else:
            config["approval_policy"] = arg
            if session.get("approval_mgr"):
                session["approval_mgr"].policy = arg
            print(f"审批策略已切换为：{arg}")
        return True

    elif command == "/stats":
        if ctx:
            stats = ctx.stats()
            print("Token 统计：")
            for k, v in stats.items():
                print(f"  {k}: {v}")
        return True

    elif command == "/sessions":
        if persistence:
            try:
                sessions = persistence.list_sessions()
                if sessions:
                    for s in sessions:
                        print(f"  {s}")
                else:
                    print("无已保存的 Session。")
            except Exception as e:
                print(f"列出 Session 失败：{e}")
        else:
            print("PersistenceManager 未初始化。")
        return True

    elif command == "/save":
        if persistence and ctx:
            try:
                sid = persistence.save_session(ctx)
                print(f"Session 已保存，ID：{sid}")
            except Exception as e:
                print(f"保存失败：{e}")
        else:
            print("PersistenceManager 未初始化。")
        return True

    elif command == "/resume":
        if not arg:
            print("用法：/resume <session_id>")
        elif persistence and ctx:
            try:
                persistence.load_session(arg, ctx)
                print(f"Session {arg} 已恢复。")
            except Exception as e:
                print(f"恢复失败：{e}")
        else:
            print("PersistenceManager 未初始化。")
        return True

    elif command == "/tools":
        if registry:
            tools = registry.list_tools()
            print(f"已注册工具（共 {len(tools)} 个）：")
            for t in tools:
                print(f"  {t.name:20s} [{t.kind.value}]  {t.description[:60]}")
        return True

    elif command == "/mcp":
        if mcp_manager:
            try:
                mcp_tools = mcp_manager.list_tools()
                print(f"MCP 工具（共 {len(mcp_tools)} 个）：")
                for t in mcp_tools:
                    print(f"  {t}")
            except Exception as e:
                print(f"获取 MCP 工具失败：{e}")
        else:
            print("MCP 未启用（启动时加 --no-mcp 以外的选项，或默认不启用）。")
        return True

    elif command == "/checkpoint":
        if persistence and ctx:
            try:
                cid = persistence.create_checkpoint(ctx)
                print(f"检查点已创建，ID：{cid}")
            except Exception as e:
                print(f"创建检查点失败：{e}")
        else:
            print("PersistenceManager 未初始化。")
        return True

    elif command == "/restore":
        if not arg:
            print("用法：/restore <checkpoint_id>")
        elif persistence and ctx:
            try:
                persistence.restore_checkpoint(arg, ctx)
                print(f"已恢复到检查点 {arg}。")
            except Exception as e:
                print(f"恢复检查点失败：{e}")
        else:
            print("PersistenceManager 未初始化。")
        return True

    return False  # 未识别的命令


# ── 交互式主循环 ───────────────────────────────────────────────────

async def interactive_loop(session: dict, max_turns: int):
    """交互式 REPL 主循环。"""
    print("\nAI Coding Agent 已就绪。输入 /help 查看命令，/exit 退出。")
    print("-" * 60)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break

        if not user_input:
            continue

        # 处理 / 命令
        if user_input.startswith("/"):
            handled = handle_slash_command(user_input, session)
            if not handled:
                print(f"未识别的命令：{user_input}。输入 /help 查看可用命令。")
            continue

        # 正常消息，进入 agentic loop
        result = await agentic_loop(
            session=session,
            user_message=user_input,
            max_turns=max_turns,
            verbose=True,
        )

        # 打印性能摘要
        print(f"\n[统计] 轮次={result['turns']} "
              f"工具={result['tools_called']} "
              f"耗时={result['elapsed_sec']}s "
              f"压缩={'是' if result['compressed'] else '否'}")


# ── Click 入口 ────────────────────────────────────────────────────

async def run(
    prompt: str | None,
    model: str,
    cwd: Path,
    max_turns: int,
    approval: str,
    enable_mcp: bool,
    enable_discovery: bool,
):
    """顶层协程：初始化 Agent，然后单次运行或进入交互模式。"""
    print(f"[初始化] 模型={model}  cwd={cwd}  审批策略={approval}")

    session = await create_agent(
        model=model,
        cwd=cwd,
        approval_policy=approval,
        enable_mcp=enable_mcp,
        enable_discovery=enable_discovery,
    )

    if prompt:
        # 非交互模式：执行单个任务后退出
        result = await agentic_loop(
            session=session,
            user_message=prompt,
            max_turns=max_turns,
            verbose=True,
        )
        print(f"\n[完成]")
        print(f"  轮次:         {result['turns']}")
        print(f"  工具调用:     {result['tools_called']}")
        print(f"  耗时:         {result['elapsed_sec']}s")
        print(f"  触发压缩:     {'是' if result['compressed'] else '否'}")
        stats = result.get("token_usage", {})
        if stats:
            print(f"  Token 统计:   {stats}")
    else:
        # 交互模式
        await interactive_loop(session, max_turns)

    # 关闭 LLM 连接
    if session.get("llm"):
        await session["llm"].close()


@click.command()
@click.option("--prompt", "-p", default=None, help="直接执行单个任务（非交互模式）")
@click.option("--model",  "-m", default="gpt-oss:120b", help="LLM 模型名称")
@click.option("--cwd",          default=".", type=click.Path(), help="工作目录")
@click.option("--max-turns",    default=20, help="最大轮次数")
@click.option("--approval",     default="on_request",
              type=click.Choice(["on_request", "auto", "autoEdit", "never", "YOLO"]),
              help="审批策略")
@click.option("--no-mcp",       is_flag=True, help="禁用 MCP")
@click.option("--no-discovery", is_flag=True, help="禁用 ToolDiscovery")
def main(prompt, model, cwd, max_turns, approval, no_mcp, no_discovery):
    """AI Coding Agent — 把所有模块组装成完整系统。"""
    asyncio.run(run(
        prompt=prompt,
        model=model,
        cwd=Path(cwd),
        max_turns=max_turns,
        approval=approval,
        enable_mcp=not no_mcp,
        enable_discovery=not no_discovery,
    ))


if __name__ == "__main__":
    main()
