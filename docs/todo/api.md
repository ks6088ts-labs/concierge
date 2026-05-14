---
title: Todo REST API Reference
description: Endpoints for the clean architecture Todo FastAPI app
---

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/tasks` | Create task |
| GET | `/tasks` | List tasks |
| GET | `/tasks/{task_id}` | Get task |
| PATCH | `/tasks/{task_id}` | Update task |
| POST | `/tasks/{task_id}/complete` | Complete task |
| DELETE | `/tasks/{task_id}` | Delete task |
| GET | `/healthz` | Health check |

## Example

```bash
curl -X POST http://localhost:8000/tasks -H 'content-type: application/json' -d '{"title":"buy milk"}'
```
