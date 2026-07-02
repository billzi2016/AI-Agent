# Build Your Own AI Coding Agent

Build a local AI coding agent from scratch: a Claude Code-style architecture implemented entirely on top of Ollama, without requiring any cloud API.

## Course Overview

This course breaks down the process of building an AI coding agent into 15 progressive Jupyter notebooks. Each chapter focuses on one module, and the code is designed so that running it helps explain the underlying architecture.

Final outcome: a local AI coding assistant that can read and write files, search the web, call tools, and autonomously complete coding tasks.

## Runnable Agent Package

The full agent implementation now lives in the top-level `agent/` package. The old monolithic `course/main.py` entry point has been moved into the package as `agent/main.py`, and the actual code is split by responsibility:

```text
agent/
  cli.py              # Click CLI, REPL, slash commands
  session.py          # Agent assembly and runtime session state
  loop.py             # Agentic loop and tool-call execution
  llm_client.py       # OpenAI-compatible async LLM client for Ollama
  context.py          # Messages, token accounting, context compression
  tooling.py          # Tool base class, result type, registry
  file_tools.py       # Read/write/edit/list/glob filesystem tools
  network_tools.py    # Web search and web fetch tools
  approval.py         # Approval policies and path safety checks
  persistence.py      # Session snapshots and checkpoints
  hooks.py            # Lifecycle hooks
  loop_detection.py   # Repeated action and cycle detection
  discovery.py        # Runtime custom tool discovery
  sub_agents.py       # Investigator and reviewer sub-agent examples
  mcp.py              # MCP manager boundary
```

## Tech Stack

| Component | Choice |
|-----------|--------|
| Local LLM | [Ollama](https://ollama.ai) + `gpt-oss:120b` |
| LLM client | OpenAI SDK compatible interface |
| CLI | Click |
| Terminal UI | Rich |
| Validation | Pydantic v2 |
| Token counting | tiktoken |
| Network requests | httpx async |
| Web search | duckduckgo-search |

## Course Structure

| Chapter | Topic | Core Output |
|---------|-------|-------------|
| 01 | Async LLM client | `LLMClient`, streaming output, exponential backoff retry |
| 02 | Context Manager | `ContextManager`, token counting, system prompt |
| 03 | Tool Framework | `Tool` abstract base class, `ToolRegistry`, `ToolResult` |
| 04 | File Tools | ReadFile / WriteFile / Edit / ListDir / Glob |
| 05 | Network Tools | WebSearch / WebFetch |
| 06 | Agentic Loop | Main agent loop, streaming `tool_calls` parsing |
| 07 | Session & CLI | Session object, Rich TUI, Click CLI |
| 08 | Context Compression | `ChatCompactor`, tool-output pruning |
| 09 | Approval & Safety | Five approval strategies, path safety |
| 10 | Persistence | Session archive, checkpoint recovery |
| 11 | Sub-Agents | Sub-agent pattern, tool allowlist isolation |
| 12 | MCP Protocol | Model Context Protocol, external tool integration |
| 13 | Tool Discovery | Dynamic custom tool loading through a plugin mechanism |
| 14 | Hooks & Loop Detection | Lifecycle hooks, loop detection |
| 15 | Full Agent | Full system assembly and integration tests |

## Quick Start

```bash
# 1. Install Ollama and pull the model
ollama pull gpt-oss:120b

# 2. Install dependencies
pip install openai tiktoken pydantic click rich httpx \
            duckduckgo-search toml mcp pytest

# 3. Start from Chapter 1
cd course
jupyter lab 01_ollama_llm_client.ipynb
```

## Prerequisites

- Python 3.11+
- Ollama installed and running with `ollama serve`
- Familiarity with Python async programming using `async` / `await`
- Basic experience with LLM APIs and the `messages` format

## Run the Full Agent

After completing all chapters:

```bash
# From the repository root
python -m agent                    # Interactive mode
python -m agent -p "Analyze this project"   # One-shot mode
python -m agent --approval YOLO    # Skip all confirmations
```

The package-local entry point is also available:

```bash
python agent/main.py
```

## Run Tests

The `agent/tests/` directory contains `unittest` coverage for local logic that does not require a running Ollama server:

```bash
python -m unittest discover -s agent/tests -p "test_*.py"
```

## Course Design Notes

See [PRD_AI_Agent_Course.md](./PRD_AI_Agent_Course.md) for the complete course plan and detailed specifications for every chapter.
