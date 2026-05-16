---
title: Chat REST API Reference
description: Endpoints for the clean architecture Chat FastAPI app
---

`chat-web` is the FastAPI entry point for the Chat app. It listens on
`http://localhost:8080`, serves Swagger UI at `/docs`, and ships a small
HTML/JS client at `/`.

```bash
uv run chat-web
# → Uvicorn running on http://0.0.0.0:8080
```

## Pages and ports

| URL | What it is |
|---|---|
| <http://localhost:8080/> | Built-in chat UI (Japanese labels) |
| <http://localhost:8080/docs> | Swagger UI (interactive REST docs) |
| <http://localhost:8080/openapi.json> | OpenAPI schema |
| <http://localhost:8080/healthz> | Liveness probe (`{"status":"ok"}`) |

## Authentication

Every endpoint that touches a conversation requires the caller to identify
themselves via the `X-User-Id` header. The value must be a UUID; FastAPI
returns `422` otherwise. The bundled web client generates and stores one for
you; from a script, generate one once and reuse it:

```bash
export USER_ID=$(python -c 'import uuid; print(uuid.uuid4())')
```

## Endpoints at a glance

| Method | Path | Description |
|---|---|---|
| POST | `/conversations` | Create conversation |
| GET | `/conversations` | List conversations (`?mine=true` filters to your own) |
| GET | `/conversations/{conversation_id}` | Get conversation |
| DELETE | `/conversations/{conversation_id}` | Delete conversation |
| POST | `/conversations/{conversation_id}/participants` | Join conversation |
| POST | `/conversations/{conversation_id}/messages` | Post a user message (no bot reply; agent reply is a separate request) |
| GET | `/conversations/{conversation_id}/messages` | List messages |
| POST | `/conversations/{conversation_id}/agent-replies` | Stream an AI agent reply over Server-Sent Events |
| GET | `/healthz` | Health check |
| GET | `/` | Static HTML front-end |

## End-to-end curl walkthrough

This is a copy-pasteable script that exercises every read/write endpoint
once.

```bash
export USER_ID=$(python -c 'import uuid; print(uuid.uuid4())')

# Create
CONV_ID=$(curl -s -X POST http://localhost:8080/conversations \
  -H "X-User-Id: ${USER_ID}" -H 'content-type: application/json' \
  -d '{"title":"general","display_name":"alice"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "CONV_ID=$CONV_ID"

# List
curl -s -H "X-User-Id: ${USER_ID}" http://localhost:8080/conversations

# Get
curl -s -H "X-User-Id: ${USER_ID}" \
  "http://localhost:8080/conversations/${CONV_ID}"

# Post a message
curl -s -X POST "http://localhost:8080/conversations/${CONV_ID}/messages" \
  -H "X-User-Id: ${USER_ID}" -H 'content-type: application/json' \
  -d '{"content":"hello","display_name":"alice"}'

# List messages
curl -s -H "X-User-Id: ${USER_ID}" \
  "http://localhost:8080/conversations/${CONV_ID}/messages"

# Delete
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X DELETE \
  -H "X-User-Id: ${USER_ID}" \
  "http://localhost:8080/conversations/${CONV_ID}"
# → HTTP 204
```

Sample `ConversationResponse`:

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "general",
  "participants": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
      "kind": "USER",
      "display_name": "alice"
    }
  ],
  "created_at": "2026-05-14T06:03:22.642785Z",
  "updated_at": "2026-05-14T06:03:22.642785Z"
}
```

Sample `MessageResponse`:

```json
{
  "id": "ac815590-189b-42c4-92a0-a9a9874e87c0",
  "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "sender": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
    "kind": "USER",
    "display_name": "alice"
  },
  "role": "USER",
  "content": "hello",
  "created_at": "2026-05-14T06:03:23.000000Z"
}
```

## Status codes

| Status | When |
|---|---|
| `200 OK` | Successful GETs |
| `201 Created` | Successful POSTs that create resources |
| `204 No Content` | Successful DELETE `/conversations/{id}` |
| `404 Not Found` | `conversation_id` does not exist |
| `503 Service Unavailable` | `AZURE_AI_PROJECT_ENDPOINT` is not configured when calling `/agent-replies` |
| `422 Unprocessable Entity` | Bad request body or non-UUID `X-User-Id` |

## AI agent reply endpoint

`POST /conversations/{conversation_id}/messages` is intentionally agent-free:
it only persists the caller's message. AI replies live behind a dedicated
endpoint so client apps can opt-in explicitly. See
[AI chatbot replies (optional)](index.md#ai-chatbot-replies-optional) for
the setup steps.

### Streaming reply via `POST .../agent-replies`

The endpoint returns a **Server-Sent Events** stream so the client can
render the reply incrementally and never has to poll. The response uses
`Content-Type: text/event-stream` and emits the following events:

| Event | Data | Notes |
|---|---|---|
| `delta` | `{"content": "<chunk>"}` | Emitted once per partial token. Concatenate `content` values in order. |
| `complete` | `MessageResponse` JSON | Final event with the persisted `AGENT` message. |
| `error` | `{"detail": "<message>"}` | Emitted instead of `complete` if generation fails mid-stream. |

Synchronous validation runs **before** the stream starts, so unknown
conversation IDs and missing configuration are surfaced via the regular
JSON error response.

| Status | When | Body |
|---|---|---|
| `200 OK` | Stream opened — events follow | `text/event-stream` |
| `404 Not Found` | `conversation_id` does not exist | `{"detail": "..."}` |
| `503 Service Unavailable` | `AZURE_AI_PROJECT_ENDPOINT` is not configured | `{"detail": "..."}` |

```bash
curl -N -s -X POST "http://localhost:8080/conversations/${CONV_ID}/agent-replies" \
  -H "X-User-Id: ${USER_ID}"
# event: delta
# data: {"content": "Hello"}
#
# event: delta
# data: {"content": "! How can I help?"}
#
# event: complete
# data: {"id": "...", "role": "AGENT", ...}
```

The `complete` event payload matches the `MessageResponse` schema:

```json
{
  "id": "f1c1e4cb-...",
  "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "sender": {
    "id": "00000000-0000-0000-0000-000000000001",
    "kind": "AGENT",
    "display_name": "Concierge AI"
  },
  "role": "AGENT",
  "content": "Hello! How can I help?",
  "created_at": "2026-05-14T06:03:23.000000Z"
}
```
