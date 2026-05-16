---
title: Cloud Agent REST API Reference
description: REST API endpoints for the Cloud Agent async task dispatch app
---

## Boot the API

```bash
uv run cloud-agent-web
```

The server listens on `http://localhost:8081`. Open
[`http://localhost:8081/docs`](http://localhost:8081/docs) for the interactive
Swagger UI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/cloud-agent/tasks` | Dispatch a new task |
| GET | `/cloud-agent/tasks` | List tasks (with optional filters) |
| GET | `/cloud-agent/tasks/{id}` | Get task by ID (for polling) |
| PATCH | `/cloud-agent/tasks/{id}` | Update task result (internal / worker use) |
| DELETE | `/cloud-agent/tasks/{id}` | Cancel a task |
| GET | `/cloud-agent/agents` | List registered agent types |
| GET | `/healthz` | Health check |

## POST /cloud-agent/tasks

Dispatch a new task to the queue.

**Request body:**

```json
{
  "agent_type": "echo",
  "payload": {"message": "hello"},
  "max_retries": 3
}
```

- `agent_type` — registered agent identifier (required, 1–100 chars)
- `payload` — dict forwarded to the agent (max 64 KiB)
- `max_retries` — override default max retries (optional)

**Response `201 Created`:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "echo",
  "payload": {"message": "hello"},
  "status": "QUEUED",
  "result": null,
  "error": null,
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z",
  "started_at": null,
  "finished_at": null
}
```

**Error codes:**
- `400` — unknown `agent_type`
- `413` / `422` — validation error (payload too large, invalid fields)

## GET /cloud-agent/tasks

List tasks with optional query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | enum | Filter by `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `DEAD_LETTER` |
| `agent_type` | string | Filter by agent type |
| `limit` | int | Max results (default 100) |
| `offset` | int | Pagination offset (default 0) |

## GET /cloud-agent/tasks/{id}

Get a specific task by UUID. Use this endpoint to poll for task completion.

**Response `200 OK`** — same schema as dispatch response.

**Error codes:** `404` — task not found.

## PATCH /cloud-agent/tasks/{id}

Update a task's result. Intended for internal worker use.

> **Note:** This endpoint is for internal worker processes. Protect it with a
> network policy or internal token in production environments.

**Request body:**

```json
{
  "status": "SUCCEEDED",
  "result": {"output": "done"},
  "error": null
}
```

**Error codes:** `404` — not found, `409` — invalid state transition.

## DELETE /cloud-agent/tasks/{id}

Cancel a task. Only `QUEUED` tasks can be reliably cancelled; `RUNNING` tasks
will be cancelled on a best-effort basis. Returns `409` if the task is already
`SUCCEEDED`, `FAILED`, or `DEAD_LETTER`.

**Response `204 No Content`** on success.

## GET /cloud-agent/agents

List all registered agent types.

**Response `200 OK`:**

```json
{
  "agent_types": ["echo"]
}
```

## Error Response Format

All error responses follow the format:

```json
{"detail": "Human-readable error message"}
```

| Status | Cause |
|--------|-------|
| 400 | Unknown `agent_type` |
| 404 | Task not found |
| 409 | Invalid state transition |
| 413 / 422 | Validation error |
| 503 | Queue backend unavailable |
