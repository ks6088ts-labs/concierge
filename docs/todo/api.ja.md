---
title: Todo API
description: FastAPI ベース Todo アプリの REST API リファレンス
---

# Todo API

## エンドポイント

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}`
- `POST /tasks/{task_id}/complete`
- `DELETE /tasks/{task_id}`
- `GET /healthz`

ローカルで起動して、自動生成される OpenAPI UI を確認できます。

```bash
uv run python -m concierge.todo.web_main
# http://127.0.0.1:8000/docs を開く
```
