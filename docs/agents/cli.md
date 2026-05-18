---
title: Agents CLI Reference
description: Standalone CLI to exercise the shared agent runtime
---

## Installation

The `agents-cli` entry point is installed automatically when you run
`uv sync`.

```bash
uv run agents-cli --help
```

`agents-cli` calls `Agent.handle(AgentRequest)` directly against the shared
registry, so you can smoke-test a registered agent without bringing up the
`cloud_agent` task queue or the `chat` conversation flow.

## Global observability options

- `--tracing` toggles shared tracing state (`concierge-agents` tracer name).
- `--mlflow` enables `mlflow.langchain.autolog()` bootstrap.
- `--verbose` enables DEBUG logging.

Environment defaults (`CONCIERGE_TRACING_ENABLED` /
`CONCIERGE_MLFLOW_ENABLED`) are applied first via `bootstrap_from_env`, then
the explicit flags override.

## Commands

### List registered agent types

```bash
uv run agents-cli list
```

Output:

```json
["echo", "langgraph-echo"]
```

### Invoke an agent

Invokes `Agent.handle()` and prints `AgentResponse` as JSON. Exit code is
`0` when `status == "succeeded"` and `1` otherwise.

```bash
# Explicit JSON payload
uv run agents-cli invoke \
  --agent-type echo \
  --payload '{"message": "hello world"}'

# Shortcut: --message merges {"message": value} into --payload
uv run agents-cli invoke --agent-type echo --message "hello world"

# Pass request context (e.g. correlation IDs)
uv run agents-cli invoke \
  --agent-type echo \
  --message "hello" \
  --context '{"task_id": "00000000-0000-0000-0000-000000000001"}'
```

Both built-in agents (`echo` and `langgraph-echo`) read `payload.message`,
so the same shortcut works for both:

```bash
uv run agents-cli invoke --agent-type langgraph-echo --message "Hello LangGraph"
```

A successful `langgraph-echo` response looks like:

```json
{
  "status": "succeeded",
  "result": {
    "echo": "Hello LangGraph",
    "reply": "Hello LangGraph",
    "tool_calls": [
      {"name": "echo", "args": {"text": "Hello LangGraph"}}
    ]
  },
  "error": null
}
```

Options:

| Flag | Required | Description |
|------|----------|-------------|
| `--agent-type` | Yes | Registered agent identifier |
| `--payload` | No | JSON object string (default `{}`) |
| `--context` | No | JSON object string passed as `AgentRequest.context` (default `{}`) |
| `--message` | No | Shortcut; merges `{"message": <value>}` into `--payload` |

### Show agent metadata

```bash
uv run agents-cli info --agent-type langgraph-echo
```

Output:

```json
{
  "agent_type": "langgraph-echo",
  "class": "LangGraphEchoAgent",
  "module": "concierge.agents.infrastructure.langgraph_echo_agent",
  "settings": {
    "langgraph_model": "azure_ai:gpt-5",
    "langgraph_system_prompt": "You are a minimal echo agent. ..."
  }
}
```

The command does not instantiate any LLM client, so it is safe to run
without Azure credentials.

## Configuration

The agents CLI only reads `AGENTS_*` variables. Repository / queue backends
belong to the `cloud_agent` and `chat` services and are not relevant here.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTS_LANGGRAPH_MODEL` | `azure_ai:gpt-5` | Model string for `init_chat_model` used by `langgraph-echo` |
| `AGENTS_LANGGRAPH_SYSTEM_PROMPT` | _(built-in)_ | System prompt for `langgraph-echo` |
| `CONCIERGE_TRACING_ENABLED` | `false` | Enable tracing without passing `--tracing` |
| `CONCIERGE_MLFLOW_ENABLED` | `false` | Enable MLflow autologging without passing `--mlflow` |

See the [Shared Agent Runtime overview](index.md) for the full agent
catalogue and contract reference.

## Running with tracing and MLflow

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<your-foundry-endpoint>"
az login
uv run agents-cli \
  --tracing --mlflow --verbose \
  invoke --agent-type langgraph-echo --message "trace me"
```
