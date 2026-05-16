---
title: Cloud Agent CLI Reference
description: CLI commands for cloud_agent task dispatch and worker
---

## Installation

The `cloud-agent-cli` entry point is installed automatically when you run
`uv sync`.

```bash
uv run cloud-agent-cli --help
```

## Task Commands

### Dispatch a task

```bash
uv run cloud-agent-cli task dispatch \
  --agent-type echo \
  --payload '{"message": "hello world"}'
```

Options:

| Flag | Required | Description |
|------|----------|-------------|
| `--agent-type` | Yes | Registered agent identifier |
| `--payload` | No | JSON string (default `{}`) |
| `--max-retries` | No | Override default max retries |

**Output** (JSON):

```json
{
  "id": "550e8400-...",
  "agent_type": "echo",
  "status": "QUEUED",
  ...
}
```

### Get a task by ID

```bash
uv run cloud-agent-cli task get <uuid>
```

### List tasks

```bash
# All tasks
uv run cloud-agent-cli task list

# Filter by status
uv run cloud-agent-cli task list --status QUEUED

# Filter by agent type
uv run cloud-agent-cli task list --agent-type echo

# Pagination
uv run cloud-agent-cli task list --limit 10 --offset 20
```

### Cancel a task

```bash
uv run cloud-agent-cli task cancel <uuid>
```

## Worker Command

The worker polls the task queue and executes tasks using registered agents.

```bash
# Run the worker indefinitely
uv run cloud-agent-cli worker

# Run for a fixed number of iterations (useful for testing)
uv run cloud-agent-cli worker --max-iterations 5
```

The worker handles `SIGINT` / `SIGTERM` gracefully — it finishes any task in
progress before shutting down.

You can also run the worker directly as a Python module:

```bash
python -m concierge.cloud_agent.infrastructure.cli.worker
```

## Agent List Command

```bash
uv run cloud-agent-cli agents
```

Output:

```json
["echo"]
```

## Configuration

All settings are controlled by environment variables (or a `.env` file).

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUD_AGENT_REPOSITORY_BACKEND` | `memory` | `memory` / `postgres` / `azure-postgres` |
| `CLOUD_AGENT_TABLE_NAME` | `cloud_agent_tasks` | SQL table name |
| `CLOUD_AGENT_QUEUE_BACKEND` | `memory` | `memory` / `azure-storage-queue` |
| `CLOUD_AGENT_QUEUE_NAME` | `cloud-agent-tasks` | Main queue name |
| `CLOUD_AGENT_DLQ_NAME` | `cloud-agent-dlq` | Dead letter queue name |
| `CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL` | — | Azure Storage queue endpoint (Entra ID auth via `DefaultAzureCredential`) |
| `CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS` | `60` | Queue visibility timeout |
| `CLOUD_AGENT_MAX_RETRIES` | `3` | Default max retries |
| `CLOUD_AGENT_WORKER_CONCURRENCY` | `1` | Worker concurrency (future) |
| `CLOUD_AGENT_POLL_INTERVAL_SECONDS` | `1.0` | Polling interval when queue empty |

See the [Configuration section in the Overview](index.md#configuration) for
backend selection tables and end-to-end `.env` examples.

## Example: Azure Storage Queue backend

Authentication uses Microsoft Entra ID via `DefaultAzureCredential`.
Grant the signed-in principal (or managed identity) the **Storage Queue Data
Contributor** role on the storage account.

```bash
export CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
export CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL="https://<account>.queue.core.windows.net"
az login
uv run cloud-agent-cli worker
```
