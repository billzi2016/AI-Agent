# Build Your Own AI Coding Agent

Build a local AI coding agent from scratch: a Claude Code-style architecture implemented entirely on top of Ollama, without requiring any cloud API.

## Course Overview

This course breaks down the process of building an AI coding agent into 15 progressive Jupyter notebooks. Each chapter focuses on one module, and the code is designed so that running it helps explain the underlying architecture.

Final outcome: a local AI coding assistant that can read and write files, search the web, call tools, and autonomously complete coding tasks.

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
cd course
python main.py                    # Interactive mode
python main.py -p "Analyze this project"   # One-shot mode
python main.py --approval YOLO    # Skip all confirmations
```

## Course Design Notes

See [PRD_AI_Agent_Course.md](./PRD_AI_Agent_Course.md) for the complete course plan and detailed specifications for every chapter.
