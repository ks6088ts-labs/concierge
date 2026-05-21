---
title: Cloud Agent App
description: Async task dispatch with DDD clean architecture
---

## Overview

`concierge/cloud_agent` is an asynchronous task dispatch application built with
**clean architecture** (DDD layered structure). It receives tasks via a REST API,
enqueues them in a background job queue, routes them to the appropriate agent,
and returns results.

```mermaid
flowchart LR
    Client[REST Client] --> Web[FastAPI Routes]
    Web --> UC[Application Use Cases]
    CLI[Typer CLI / Worker] --> UC
    UC --> Domain[Domain Entities]
    UC --> Repo[TaskRepository]
    UC --> Queue[TaskQueue]
    UC --> Registry[AgentRegistry]
    Registry --> Echo[EchoAgent]
    Registry --> LGE[LangGraphEchoAgent]
```

## Agent Extension Point

Agents are defined in the shared `concierge/agents/` package.  Each agent
implements the `Agent` Protocol from the shared `application` layer:

```python
class Agent(Protocol):
    agent_type: ClassVar[str]
    async def handle(self, request: AgentRequest) -> AgentResponse: ...
```

The `infrastructure` layer is the only place that may import LangChain /
LangGraph.  The `domain` and `application` layers must remain framework-free
(enforced by `tests/agents/test_architecture.py` and import-linter contracts).

```mermaid
classDiagram
    class Agent {
        <<Protocol>>
        +agent_type: str
        +handle(request) AgentResponse
    }
    class EchoAgent {
        +agent_type = "echo"
        +handle(request) AgentResponse
    }
    class LangGraphEchoAgent {
        +agent_type = "langgraph-echo"
        +handle(request) AgentResponse
        -_build_agent()
    }
    Agent <|.. EchoAgent
    Agent <|.. LangGraphEchoAgent
```

## Key Design Principles

- **Queue-agnostic abstraction** — ships with `InMemory` (local dev) and
  `AzureStorageQueue` backends; switch via `CLOUD_AGENT_QUEUE_BACKEND`.
- **Agent I/O standardised** — every agent receives `AgentRequest` and returns
  `AgentResponse` (Pydantic schemas from `concierge.agents`).  The `AgentRegistry`
  maps `agent_type` strings to concrete `Agent` implementations.
- **Runtime-agnostic workers** — the worker loop runs as a local CLI process
  today; the same `Agent` interface can be reused on Azure Functions in the
  future.
- **Dead Letter Queue (DLQ)** — tasks that exceed `max_retries` are moved to a
  DLQ automatically.

## Directory Layout

```
concierge/cloud_agent/
  domain/
    entities.py        # Task dataclass with state-machine transitions
    value_objects.py   # TaskStatus enum + allowed transitions
    exceptions.py      # Domain-specific exceptions
  application/
    agents.py          # Agent Protocol, TaskInput/Output, AgentRegistry
    queues.py          # TaskQueue Protocol + QueueMessage schema
    repositories.py    # TaskRepository Protocol
    use_cases.py       # DispatchTask, GetTask, ListTasks, CancelTask, …
  infrastructure/
    persistence/       # InMemoryTaskRepository, SqlAlchemyTaskRepository
    queue/             # InMemoryTaskQueue, AzureStorageQueueTaskQueue
    web/               # FastAPI app, routes, schemas, exception handlers
    cli/               # Typer CLI app, worker loop
```

## Quick Start

```bash
# Start the REST API (in-memory backend by default)
uv run cloud-agent-web

# Run the worker (separate terminal)
uv run cloud-agent-cli worker

# Dispatch a task
uv run cloud-agent-cli task dispatch --agent-type echo --payload '{"message": "hello"}'

# List registered agents
uv run cloud-agent-cli agents
```

## Running the LangGraph Echo Agent

`LangGraphEchoAgent` (`agent_type = "langgraph-echo"`) is the reference
implementation for integrating LangChain / LangGraph agents with the
`cloud_agent` task pipeline. It uses
[`langchain.agents.create_agent`](https://python.langchain.com/) with a single
`echo` tool and an Azure-hosted chat model resolved through
`init_chat_model`.

### Prerequisites

- Azure AI Foundry (or Azure OpenAI) deployment reachable via the model
  string in `AGENTS_LANGGRAPH_MODEL` (default `azure_ai:gpt-5`).
- A principal that `DefaultAzureCredential` can resolve — typically
  `az login` for local development, or a managed identity in Azure.
- The signed-in principal must have permission to call the Foundry
  deployment (e.g. **Azure AI Developer** role).

### Minimal `.env`

The fastest setup uses both in-memory backends. The API and the worker
**must run in the same Python process** to share the queue / repository, so
this mode is only useful for embedded smoke tests. For a realistic split
(separate `cloud-agent-cli worker` and `cloud-agent-cli task dispatch`
processes), switch to `postgres` + `azure-storage-queue`.

```bash
# .env — split-process setup
CLOUD_AGENT_REPOSITORY_BACKEND=postgres
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net
AGENTS_LANGGRAPH_MODEL=azure_ai:gpt-5

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=concierge
POSTGRES_PASSWORD=concierge
POSTGRES_DB=concierge
```

### Step-by-step

```bash
# 1. Authenticate so DefaultAzureCredential can mint tokens
az login

# 2. Start dependencies (only required for postgres / azure-storage-queue)
docker compose up -d postgres

# 3. Confirm the agent is registered
uv run cloud-agent-cli agents
# → ["echo", "langgraph-echo", "github-copilot-echo", "microsoft-agent-framework-echo"]

# 4. Start the worker (terminal 1)
uv run cloud-agent-cli worker

# 5. Dispatch a task (terminal 2)
uv run cloud-agent-cli task dispatch \
  --agent-type langgraph-echo \
  --payload '{"message": "Hello LangGraph"}'

# 6. Poll for the result using the task id printed above
uv run cloud-agent-cli task get <task-id>
```

### Payload contract

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `message` | `string` | Yes | Non-empty. Forwarded verbatim to the LLM; the agent fails with `payload.message is required` otherwise. |

### Result shape

A successful task stores the following object under `result`:

```json
{
  "echo": "Hello LangGraph",
  "reply": "<final assistant message>",
  "tool_calls": [
    {"name": "echo", "args": {"text": "Hello LangGraph"}}
  ]
}
```

`reply` is the last `AIMessage.content` produced by the graph, and
`tool_calls` lists every `(name, args)` pair the model emitted while
processing the task.

### Customising the agent

- `AGENTS_LANGGRAPH_MODEL` — swap the underlying chat model (e.g.
  `azure_ai:gpt-4o-mini`).
- `AGENTS_LANGGRAPH_SYSTEM_PROMPT` — replace the built-in system prompt
  to change behaviour without writing code.
- For a new agent, copy
  [`concierge/agents/infrastructure/langgraph_echo_agent.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/agents/infrastructure/langgraph_echo_agent.py),
  add tools, and register it in
  [`concierge/agents/infrastructure/registry_factory.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/agents/infrastructure/registry_factory.py).

### Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Task stuck in `QUEUED` | Worker not running, or `memory` backend used across separate processes. Start `cloud-agent-cli worker` or switch to `postgres` + `azure-storage-queue`. |
| `status=failed`, error mentions credentials | `DefaultAzureCredential` could not resolve a principal. Run `az login` or configure a managed identity. |
| `status=failed`, `payload.message is required` | The dispatched payload is missing `message` or it is an empty / whitespace-only string. |
| 403 from the model deployment | The principal is missing the **Azure AI Developer** role on the Foundry project. |

## Task Lifecycle

```
QUEUED → RUNNING → SUCCEEDED
                 → FAILED → (retry) → QUEUED
                          → (max retries) → DEAD_LETTER
       → CANCELLED
```

---

## Configuration

All Cloud Agent settings are aggregated in
[`concierge.settings.CloudAgentSettings`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/cloud_agent.py)
and read from environment variables with the **`CLOUD_AGENT_`** prefix
(see [`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template)).
The rest of the codebase never touches `os.environ` directly — both the REST
API (`cloud-agent-web`) and the worker / dispatcher CLI (`cloud-agent-cli`)
share the exact same configuration object.

### Settings reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUD_AGENT_REPOSITORY_BACKEND` | `memory` | Task persistence backend: `memory` / `postgres` / `azure-postgres`. |
| `CLOUD_AGENT_TABLE_NAME` | `cloud_agent_tasks` | Table name used by the SQL backends. |
| `CLOUD_AGENT_QUEUE_BACKEND` | `memory` | Job queue backend: `memory` / `azure-storage-queue`. |
| `CLOUD_AGENT_QUEUE_NAME` | `cloud-agent-tasks` | Main task queue name (Azure Storage Queue resource name). |
| `CLOUD_AGENT_DLQ_NAME` | `cloud-agent-dlq` | Dead Letter Queue name (created automatically on first use). |
| `CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL` | _(empty)_ | **Required** when `CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue`. Queue service endpoint (e.g. `https://<account>.queue.core.windows.net`). Authentication is performed only via Microsoft Entra ID (`DefaultAzureCredential`); connection strings / account keys are **not** supported. |
| `CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS` | `60` | How long a dequeued message is hidden from other workers while a task is being processed. Should comfortably exceed the worst-case agent execution time. |
| `CLOUD_AGENT_MAX_RETRIES` | `3` | Default retry budget injected into `DispatchTaskUseCase`. A task is moved to the DLQ when `retry_count > max_retries`. Can be overridden per dispatch via the API / CLI. |
| `CLOUD_AGENT_WORKER_CONCURRENCY` | `1` | Reserved for future concurrent processing per worker. The current loop processes one task at a time; scale horizontally instead. |
| `CLOUD_AGENT_POLL_INTERVAL_SECONDS` | `1.0` | How long the worker sleeps after an empty `dequeue()` before polling again. |

LangGraph agent settings (`AGENTS_LANGGRAPH_MODEL`, `AGENTS_LANGGRAPH_SYSTEM_PROMPT`) are now
managed in the **shared agent runtime**. See [Shared Agent Runtime](../agents/index.md#configuration).

### Repository backend selection

The repository persists `Task` aggregates and is consumed by both `cloud-agent-web`
and the worker. The choice is made by `CLOUD_AGENT_REPOSITORY_BACKEND`:

| Value | Enum member | When to use | Schema init |
|-------|-------------|-------------|-------------|
| `memory` (default) | `CloudAgentRepositoryBackend.MEMORY` | Local smoke tests. Data is lost on restart and **not shared across processes** — the worker and API must run in the same process to see each other’s tasks. | Not needed |
| `postgres` | `CloudAgentRepositoryBackend.POSTGRES` | Local Docker Compose PostgreSQL using the `POSTGRES_*` variables. Tables are created lazily by `SqlAlchemyTaskRepository` on first use. | Auto |
| `azure-postgres` | `CloudAgentRepositoryBackend.AZURE_POSTGRES` | Azure Database for PostgreSQL Flexible Server using the `AZURE_*` variables. Supports Microsoft Entra ID auth via `AZURE_USE_ENTRA_AUTH=true`. | Auto |

!!! tip "`memory` and multi-process setups"
    Because `InMemoryTaskRepository` stores state in a Python dict, running
    `cloud-agent-web` and `cloud-agent-cli worker` in separate terminals
    with `memory` mode will produce two completely independent task stores.
    Switch to `postgres` (or `azure-postgres`) whenever you split processes.

### Queue backend selection

| Value | When to use | Required variables |
|-------|-------------|--------------------|
| `memory` (default) | Local smoke tests. Uses an in-process `asyncio.Queue`. Only useful when the API and the worker live in the same Python process. | — |
| `azure-storage-queue` | Production-grade durable queue. The main queue and DLQ are auto-created on startup. Auth is Entra ID only via `DefaultAzureCredential`. | `CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL` |

The factory raises `ValueError` if `azure-storage-queue` is selected without an
account URL. Authentication is performed exclusively via Microsoft Entra ID
using `DefaultAzureCredential` — the calling principal must hold the
**Storage Queue Data Contributor** role (or equivalent custom RBAC) on the
storage account. Visibility timeouts and DLQ routing are driven by
`CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS` and `CLOUD_AGENT_DLQ_NAME`.

### Example: local development (memory only)

```bash
# .env (minimum)
CLOUD_AGENT_REPOSITORY_BACKEND=memory
CLOUD_AGENT_QUEUE_BACKEND=memory
```

Run the API and worker in the **same process group** so they share the
in-memory store and queue. The simplest way is to keep them in one terminal
each but understand they will use independent in-memory state — use this mode
only for unit-style end-to-end checks.

### Example: PostgreSQL + Azure Storage Queue

```bash
# .env
CLOUD_AGENT_REPOSITORY_BACKEND=postgres
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net
CLOUD_AGENT_QUEUE_NAME=cloud-agent-tasks
CLOUD_AGENT_DLQ_NAME=cloud-agent-dlq
CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS=120
CLOUD_AGENT_MAX_RETRIES=5

# Local Postgres connection (shared with the Chat / Todo apps)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=concierge
POSTGRES_PASSWORD=concierge
POSTGRES_DB=concierge
```

```bash
docker compose up -d postgres
az login                       # so DefaultAzureCredential can mint a token
uv run cloud-agent-web        # terminal 1
uv run cloud-agent-cli worker # terminal 2
```

Grant the signed-in principal (or managed identity) the **Storage Queue Data
Contributor** role on the target storage account before starting the
services.

### Example: Azure Database for PostgreSQL (Entra ID) + Azure Storage Queue

```bash
# .env
CLOUD_AGENT_REPOSITORY_BACKEND=azure-postgres
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net

AZURE_DBHOST=<server-name>.postgres.database.azure.com
AZURE_DBNAME=postgres
AZURE_USE_ENTRA_AUTH=true
AZURE_DBUSER=<entra-principal>
```

Ensure `DefaultAzureCredential` can mint a token (e.g. `az login` or a
managed identity) before starting the API / worker. The same principal must
have the **Storage Queue Data Contributor** role on the storage account in
addition to the PostgreSQL role used for `AZURE_DBUSER`.
