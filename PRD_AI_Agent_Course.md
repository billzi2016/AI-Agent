# PRD：从零手搓 AI Coding Agent — 本地 LLM 实战课

> 基于 Ollama + gpt-oss:120b，复刻 Claude Code 核心架构

---

## 一、这门课是什么

视频里那个人从头写了一个 Claude Code 级别的 AI 编码 Agent，用的是 Anthropic API。

这门课把它换成本地跑的 Ollama（gpt-oss:120b），然后一步一步把每个模块拆开来，用 Jupyter Notebook 写清楚——不是讲 PPT，是真的跑代码。

学完之后你手上有一个能用的 AI Agent，不依赖任何云 API，完全本地运行。

---

## 二、面向谁

- 会 Python，写过异步代码（`async/await`）
- 用过 LLM API，知道 messages 列表怎么构造
- 想搞清楚 Cursor/Claude Code 这类工具背后在做什么

不需要懂 ML，不需要读过论文。

---

## 三、技术栈

| 组件 | 选型 |
|------|------|
| 本地 LLM | Ollama + `gpt-oss:120b` |
| LLM 客户端 | OpenAI SDK（`base_url` 指向 Ollama） |
| CLI | Click |
| 终端 UI | Rich |
| 参数验证 | Pydantic v2 |
| Token 计数 | tiktoken（fallback: `len/4`） |
| 网络请求 | httpx（async） |
| 网络搜索 | duckduckgo-search（DDGS） |
| 配置文件 | TOML |

---

## 四、Notebook 结构

### Module 1 — 打地基

#### `01_ollama_llm_client.ipynb`

**造什么**：异步 LLM 客户端，封装 Ollama

**具体内容**：
- 用 OpenAI SDK 对接 Ollama（`base_url="http://localhost:11434/v1"`）
- 实现 `chat_completion(messages, stream=False)`
- 实现流式版本：`stream=True` 时 yield `text_delta` 事件
- 加指数退避重试：1s → 2s → 4s，捕获 `RateLimitError`、`APIConnectionError`
- 在 Notebook 里跑：问 gpt-oss:120b 一个代码问题，看流式输出

**为什么这么做**：Ollama 完全兼容 OpenAI API 格式，同一套客户端代码以后可以无缝换成 OpenRouter 或 Anthropic，只改 `base_url`。

---

#### `02_context_manager.ipynb`

**造什么**：对话历史管理器

**具体内容**：
- 定义 `MessageItem(role, content, token_count)`
- 实现 `add_user_message()` / `add_assistant_message()` / `get_messages()`
- 写 token 计数：优先用 tiktoken，失败降级到 `len(text) // 4`
- 写系统 prompt（身份描述、工具使用规则、安全规则）
- 测试：构造一段多轮对话，验证消息顺序和 token 统计

**为什么这么做**：LLM 本身无状态。每次请求你必须把完整历史带上去，Context Manager 就是管理这个历史的地方。

---

### Module 2 — 工具系统

#### `03_tool_framework.ipynb`

**造什么**：工具抽象基类 + 注册表

**具体内容**：
- 定义 `ToolKind` 枚举：`READ / WRITE / SHELL / NETWORK / MEMORY / MCP`
- 抽象基类 `Tool`：必须实现 `name`、`description`、`schema()`、`execute()`、`validate()`、`is_mutating()`
- 定义 `ToolInvocation` 和 `ToolResult`（`success_result` / `error_result`）
- 写 `ToolRegistry`：`register()` / `unregister()` / `get_schemas()` / `invoke()`
- `invoke()` 内部做：取工具 → 验证参数 → 执行 → 捕获异常 → 返回统一 `ToolResult`
- 演示：注册一个假 `EchoTool`，调用它，看 `ToolResult` 结构

**为什么这么做**：所有工具走同一个接口，LLM 看到的是统一 JSON Schema，Agent 调用工具也是统一入口，不用一堆 if-else 判断工具类型。

---

#### `04_file_tools.ipynb`

**造什么**：5 个文件系统工具

**具体内容**：

**ReadFileTool**
- 参数：`path`、`offset`（行号）、`limit`（行数）
- 实现：路径解析、二进制文件检测、10MB 大小限制、带行号输出、token 截断
- 安全规则：只能读工作目录及其子目录

**WriteFileTool**
- 参数：`path`、`content`、`create_directories`（默认 true）
- 实现：读旧内容 → 创建父目录 → 写入 → 生成 unified diff
- `FileDiff` 数据类：用 `difflib.unified_diff` 生成 diff 字符串

**EditTool**
- 参数：`path`、`old_string`、`new_string`、`replace_all`（默认 false）
- 实现：精确字符串搜索替换，未匹配时返回有意义的错误（让 LLM 能纠正）

**ListDirectoryTool**
- 参数：`path`（默认 `.`）、`include_hidden`（默认 false）
- 输出：目录加斜杠，排序，带条目数元数据

**GlobTool**
- 参数：`pattern`（如 `**/*.py`）、`search_path`（默认 `.`）
- 实现：`Path.glob`，只返回文件，最多 500 条，超出提示截断

---

#### `05_network_tools.ipynb`

**造什么**：2 个网络工具

**具体内容**：

**WebSearchTool**
- 用 `duckduckgo-search` 的 `DDGS`
- 参数：`query`、`max_results`（1-20，默认 10）
- 返回每条结果的 `title` / `href` / `body`

**WebFetchTool**
- 用 `httpx.AsyncClient`
- 参数：`url`（必须 http/https）、`timeout`（默认 120s）
- 实现：验证 URL → GET 请求 → 处理重定向/状态码错误/超时 → 超过 100KB 截断
- 演示：抓一个文档页面，提取关键内容给 LLM 分析

---

### Module 3 — Agent 核心

#### `06_agentic_loop.ipynb`

**造什么**：Agent 主循环

**具体内容**：
- 定义 `AgentEvent` 枚举：`agent_start / agent_end / text_delta / text_complete / tool_call_start / tool_call_complete / round_start / round_end`
- 实现 `AgenticLoop` 异步生成器：
  1. 写用户消息到 Context Manager
  2. 调用 LLM（带工具 schema）
  3. 解析流式 delta，`yield AgentEvent`
  4. 识别 `tool_calls`，调用 `registry.invoke()`
  5. 把工具结果写回 Context Manager，继续下一轮
  6. 没有 `tool_calls` 时退出循环
- 演示：让 Agent 自主读一个文件然后写一个 summary

**这是整门课的核心**：工具调用是怎么循环起来的，在这个 Notebook 里看得最清楚。

---

#### `07_session_and_cli.ipynb`

**造什么**：Session 对象 + 基础 CLI

**具体内容**：
- `Session` 类：`session_id`（uuid4）、`created_at`、`updated_at`、`turn_count`、`context_manager`、`tool_registry`、`llm_client`、`config`
- `increment_turn()` 方法
- 用 Click 包装 CLI：`--prompt`（一次性）+ 交互式模式
- 用 Rich 写终端 UI：
  - 流式文本实时打印
  - 工具调用显示面板（工具名、参数表格、代码高亮）
  - 彩色错误提示
- 支持 `/help` `/exit` `/clear` `/stats` `/tools`

---

### Module 4 — 稳定性机制

#### `08_context_compression.ipynb`

**造什么**：上下文自动压缩

**具体内容**：
- 压缩触发条件：`total_tokens > 0.8 × context_window`（gpt-oss:120b 约 128k）
- `ChatCompactor`：把历史消息格式化（去系统 prompt，只保留关键内容，超 2000 字符截断），调用 LLM 非流式生成摘要，返回摘要字符串 + token 用量
- 工具输出剪枝：保留最近 40k token，可裁掉更早的工具结果
- Token 追踪：`latest_usage` + `total_usage`，`set_latest_usage()` + `add_usage()`
- 演示：构造一个超长对话，触发压缩，验证摘要质量

---

#### `09_approval_and_safety.ipynb`

**造什么**：审批系统 + 安全策略

**具体内容**：
- 可变更工具（WriteFile、Edit、Shell）的 `get_confirmation()` 方法
- `approval` 策略枚举：`on_request / auto / autoEdit / never / YOLO`
- `ApprovalManager`：根据策略、命令安全性、路径安全性决定 `approved / rejected / needs_confirmation`
- 路径安全：只允许工作目录及子目录
- 演示：在 `auto` 和 `on_request` 模式下让 Agent 写文件，看行为差异

---

#### `10_persistence_and_checkpoint.ipynb`

**造什么**：会话持久化 + 检查点

**具体内容**：
- `PersistenceManager`：管理 `sessions/` 和 `checkpoints/` 目录
- `SessionSnapshot`：`session_id / created_at / updated_at / turn_count / messages / total_usage`，序列化为 JSON，权限 600
- `save_session()` / `load_session()` / `list_sessions()` / `clear()` / `prune()`
- 检查点：`/checkpoint` → 生成 `sessionID_YYYYMMDD_HHMMSS.json`，`/restore checkpoint_id` → 恢复
- 演示：跑一个任务，创建检查点，关掉进程，从检查点恢复继续对话

---

### Module 5 — 高级特性

#### `11_sub_agents.ipynb`

**造什么**：子代理模式

**具体内容**：
- 主代理什么时候用子代理：任务复杂、跨文件、上下文快满时
- 实现两个示例子代理：
  - `CodebaseInvestigator`：只读工具白名单（ReadFile、ListDir、Glob），调查代码库
  - `CodeReviewer`：审查代码质量，只需 ReadFile
- `SubAgentParameters`：`action`、`content`、`max_turns`、`timeout`
- 演示：主代理接到"重构这个模块"的任务，先派 Investigator 调查，再自己动手修改

---

#### `12_mcp_protocol.ipynb`

**造什么**：MCP 协议集成

**具体内容**：
- MCP 是什么：标准化 AI 与外部工具交互的协议，类比 USB 接口
- 支持三种传输方式：stdin/stdout、HTTP、SSE
- 用 `fast-mcp` 库实现 `MCPClient`：`connect()` / `list_tools()` / `call_tool()` / `disconnect()`
- 连接状态管理：`disconnected → connecting → connected → error`
- `MCPManager`：并行启动所有 MCP 服务器（`asyncio.gather`）
- `config.toml` 里的 MCP 配置：`enabled`、`command/args`（本地）或 `url`（网络）
- 演示：写一个简单 MCP 服务器（暴露一个 `run_tests` 工具），从 Agent 调用它

---

#### `13_tool_discovery.ipynb`

**造什么**：运行时动态工具加载

**具体内容**：
- 扫描 `.ai_agent/tools/*.py`（忽略 `__init__.py` / `__main__.py`）
- 用 `importlib.util.spec_from_file_location` 动态 import
- 检查类是否继承自 `Tool`，实例化后注册到全局注册表
- 演示：在 `.ai_agent/tools/` 写一个自定义工具（比如 `RunPytestTool`），不修改任何核心代码，重启 Agent 后自动可用

---

#### `14_hooks_and_loop_detection.ipynb`

**造什么**：钩子系统 + 循环检测

**具体内容**：

**Hooks**
- `HookTrigger` 枚举：`before_agent / after_agent / before_tool / after_tool / on_error`
- 在 `config.toml` 里配置 `command` 或 `script`、`timeout`、`enabled`
- `HookSystem.trigger_*`：执行命令，传环境变量（`AI_AGENT_CURRENT_WORKING_DIRECTORY` 等）
- 用例：每次工具调用后自动运行 linter

**LoopDetector**
- 记录动作签名（工具名 + 参数 hash）
- 检测精确重复（超过 `max_exact_repeats`）
- 检测循环模式（重复序列长度超过 `max_cycle_length`）
- 检测到后：返回错误，在系统 prompt 里提示 LLM 改变策略
- 演示：构造一个会让 LLM 陷入循环的场景，看检测器介入

---

### Module 6 — 完整系统

#### `15_full_agent.ipynb`

**造什么**：把前 14 个模块组装成完整 Agent

**具体内容**：
- 完整初始化流程：加载配置 → 创建 Session → 初始化 MCPManager → ToolDiscovery → 注册所有工具
- 完整 CLI：所有命令 `/help / exit / clear / config / model / approval / stats / sessions / save / resume / tools / mcp / checkpoint / restore`
- 集成测试：给 Agent 一个真实任务（比如"分析这个 Python 项目的结构，找出所有 TODO 注释，生成报告"），全程跑完，观察每个模块的行为
- 性能数据：记录每轮的 token 消耗、是否触发压缩、工具调用次数

---

## 五、每个 Notebook 的结构

每个 Notebook 统一格式：

```
1. 这个模块解决什么问题（1 段，说清楚，不废话）
2. 核心数据结构（代码 + 注释）
3. 实现（分步写，每步可运行）
4. 单元测试（直接在 Notebook 里跑 assert）
5. 和 Ollama 集成测试（真实调用，看输出）
6. 坑点说明（遇到过的真实 bug，怎么修）
```

---

## 六、前置要求

```bash
# 本地跑 Ollama
ollama pull gpt-oss:120b

# Python 依赖
pip install openai anthropic tiktoken pydantic click rich httpx \
            duckduckgo-search toml fast-mcp pytest
```

---

## 七、课程产出

学完之后你有：
1. 一个能在本地运行的 AI 编码 Agent（不依赖云 API）
2. 每个核心模块的独立实现（可以单独拿出来用）
3. 对 Claude Code / Cursor 这类工具架构的清晰理解

---

## 八、开发顺序

| 优先级 | Notebook | 原因 |
|--------|----------|------|
| P0 | 01, 02, 03 | 后面所有模块都依赖这三个 |
| P1 | 04, 05, 06, 07 | 最小可运行 Agent |
| P2 | 08, 09, 10 | 生产可用 |
| P3 | 11, 12, 13, 14 | 高级特性 |
| P4 | 15 | 集成 |
