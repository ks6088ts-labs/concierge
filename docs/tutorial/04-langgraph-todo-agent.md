---
title: Step 4 - LangGraph Todo Agent CLI
description: Build a LangGraph ReAct agent CLI that operates the Todo Web API through tools
---

# Step 4 - LangGraph Todo Agent CLI

## Overview

This step adds a minimal LangGraph + Microsoft Foundry CLI at
`scripts/langgraph/vanilla.py`.

The agent talks to the Todo Web API through tools and supports:

- one-shot mode: `run`
- interactive mode: `chat`

## Prerequisites

Start the Todo API in another terminal:

```bash
uv run todo-web
```

Make sure your `.env` contains Microsoft Foundry settings (same as previous
steps).

## Usage

### One-shot mode

```bash
uv run python scripts/langgraph/vanilla.py run \
  --query "牛乳を買うタスクを追加して、その後一覧を見せて"
```

### Interactive mode

```bash
uv run python scripts/langgraph/vanilla.py chat \
  --endpoint http://localhost:8000
```

Common options:

- `--endpoint/-e`: Todo API base URL (CLI value > `TODO_API_ENDPOINT` > default)
- `--model/-M`: model string for `init_chat_model`
- `--timeout`: HTTP timeout seconds
- `--thread-id`: LangGraph thread id

`chat` also supports `--system` for overriding the system prompt.

## Slash commands (`chat`)

- `/exit`, `/quit`: leave REPL
- `/reset`: reset conversation thread id
- `/help`: show commands and tools
- `/tools`: show tool signatures
- `/thread`: show current thread id

## Observability

Like `scripts/microsoft_foundry/vanilla.py`, this CLI supports:

- `--tracing/-t`: Azure Monitor / Foundry tracing
- `--mlflow/-m`: MLflow autologging
- `--verbose/-v`: DEBUG logs

Example:

```bash
uv run python scripts/langgraph/vanilla.py -t -m chat
```

## Troubleshooting

If the Todo API is unreachable or returns 4xx/5xx, tools return structured
error dictionaries (instead of throwing), so the agent can retry or recover.

Check:

1. `todo-web` is running
2. `--endpoint` points to the correct host/port
3. request/response details under `--verbose`
