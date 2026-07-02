# Build Your Own AI Coding Agent

从零手搓一个本地 AI Coding Agent——复刻 Claude Code 核心架构，完全基于 Ollama（无需云 API）。

## 课程简介

这门课把「如何构建 AI Coding Agent」这件事拆成 15 个渐进式 Jupyter Notebook，每章聚焦一个模块，跑完代码就能理解原理。

最终产物：一个跑在本地的 AI 编码助手，能读写文件、搜索网络、调用工具，自主完成代码任务。

## 可运行 Agent 包

完整 Agent 实现现在放在仓库根目录的 `agent/` 包中。原来单文件式的 `course/main.py` 已经移动为包内入口 `agent/main.py`，实际逻辑按职责拆分：

```text
agent/
  cli.py              # Click CLI、交互式 REPL、slash commands
  session.py          # Agent 装配和运行时 Session
  loop.py             # Agentic loop 与工具调用执行
  llm_client.py       # 面向 Ollama 的 OpenAI 兼容异步 LLM 客户端
  context.py          # messages、token 统计、上下文压缩
  tooling.py          # 工具基类、返回值、注册表
  file_tools.py       # 读写编辑、列目录、glob 文件工具
  network_tools.py    # Web 搜索与网页抓取工具
  approval.py         # 审批策略与路径安全检查
  persistence.py      # Session 快照与检查点
  hooks.py            # 生命周期 Hooks
  loop_detection.py   # 重复动作和循环检测
  discovery.py        # 运行时自定义工具发现
  sub_agents.py       # Investigator / Reviewer 子代理示例
  mcp.py              # MCP 管理边界
```

## 技术栈

| 组件 | 选型 |
|------|------|
| 本地 LLM | [Ollama](https://ollama.ai) + `gpt-oss:120b` |
| LLM 客户端 | OpenAI SDK（兼容接口） |
| CLI | Click |
| 终端 UI | Rich |
| 参数验证 | Pydantic v2 |
| Token 计数 | tiktoken |
| 网络请求 | httpx（async） |
| 网络搜索 | duckduckgo-search |

## 课程结构

| 章节 | 内容 | 核心产物 |
|------|------|----------|
| 01 | 异步 LLM 客户端 | `LLMClient`，流式输出，指数退避重试 |
| 02 | Context Manager | `ContextManager`，token 计数，系统 prompt |
| 03 | Tool Framework | `Tool` 抽象基类，`ToolRegistry`，`ToolResult` |
| 04 | File Tools | ReadFile / WriteFile / Edit / ListDir / Glob |
| 05 | Network Tools | WebSearch / WebFetch |
| 06 | Agentic Loop | Agent 主循环，流式 tool_calls 解析 |
| 07 | Session & CLI | Session 对象，Rich TUI，Click CLI |
| 08 | Context Compression | ChatCompactor，工具输出剪枝 |
| 09 | Approval & Safety | 五种审批策略，路径安全 |
| 10 | Persistence | 会话存档，检查点恢复 |
| 11 | Sub-Agents | 子代理模式，工具白名单隔离 |
| 12 | MCP Protocol | Model Context Protocol，外部工具接入 |
| 13 | Tool Discovery | 动态加载自定义工具（插件机制） |
| 14 | Hooks & Loop Detection | 生命周期钩子，循环检测 |
| 15 | Full Agent | 完整系统组装，集成测试 |

## 快速开始

```bash
# 1. 安装 Ollama 并拉取模型
ollama pull gpt-oss:120b

# 2. 安装依赖
pip install openai tiktoken pydantic click rich httpx \
            duckduckgo-search toml mcp pytest

# 3. 从第一章开始
cd course
jupyter lab 01_ollama_llm_client.ipynb
```

## 前置要求

- Python 3.11+
- Ollama 已安装并运行（`ollama serve`）
- 会 Python 异步编程（`async/await`）
- 用过 LLM API（知道 messages 格式）

## 运行完整 Agent

完成全部章节后：

```bash
# 从仓库根目录运行
python -m agent                    # 交互模式
python -m agent -p "分析这个项目"   # 一次性模式
python -m agent --approval YOLO    # 跳过所有确认
```

也可以使用包内入口：

```bash
python agent/main.py
```

## 运行测试

`agent/tests/` 目录包含基于标准库 `unittest` 的测试，覆盖不需要真实 Ollama 服务的本地逻辑：

```bash
python -m unittest discover -s agent/tests -p "test_*.py"
```

## 课程设计说明

参见 [PRD_AI_Agent_Course.md](./PRD_AI_Agent_Course.md)，其中包含完整的课程规划和每章详细规格。
