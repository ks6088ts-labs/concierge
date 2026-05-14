---
title: Chat REST API Reference
description: Endpoints for the clean architecture Chat FastAPI app
---

## Boot the API

```bash
uv run chat-web
```

## Endpoints at a glance

| Method | Path | Description |
|---|---|---|
| POST | `/conversations` | Create conversation |
| GET | `/conversations` | List conversations |
| GET | `/conversations/{conversation_id}` | Get conversation |
| DELETE | `/conversations/{conversation_id}` | Delete conversation |
| POST | `/conversations/{conversation_id}/participants` | Join conversation |
| POST | `/conversations/{conversation_id}/messages` | Post message |
| GET | `/conversations/{conversation_id}/messages` | List messages |
| GET | `/healthz` | Health check |
| GET | `/` | Static HTML front-end |

## Curl examples

```bash
USER_ID=$(python -c 'import uuid; print(uuid.uuid4())')

curl -X POST http://localhost:8080/conversations \
  -H "X-User-Id: ${USER_ID}" \
  -H 'content-type: application/json' \
  -d '{"title":"general","display_name":"alice"}'
```

## Response shape

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
