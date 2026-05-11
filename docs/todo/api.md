---
title: Todo API
description: REST API reference for the FastAPI Todo application
---

# Todo API

## Endpoints

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}`
- `POST /tasks/{task_id}/complete`
- `DELETE /tasks/{task_id}`
- `GET /healthz`

Start the app locally and open the generated OpenAPI UI:

```bash
uv run python -m concierge.todo.web_main
# open http://127.0.0.1:8000/docs
```
