---
title: Todo REST API リファレンス
description: クリーンアーキテクチャ Todo FastAPI アプリのエンドポイント
---

## API サーバを起動する

```bash
uv run todo-web
```

サーバは `http://localhost:8080` で待ち受けます。ブラウザで
[`http://localhost:8080/docs`](http://localhost:8080/docs) を開くと、
FastAPI が [`/openapi.json`](http://localhost:8080/openapi.json) から自動生成した
Swagger UI が表示されます。

![Todo API Swagger UI 全体](../images/todo-api-swagger-overview.png)

## エンドポイント一覧

| Method | Path | 説明 |
|---|---|---|
| POST | `/tasks` | タスク作成 |
| GET | `/tasks` | タスク一覧 |
| GET | `/tasks/{task_id}` | タスク取得 |
| PATCH | `/tasks/{task_id}` | タスク更新 |
| POST | `/tasks/{task_id}/complete` | タスク完了（`status -> DONE`） |
| DELETE | `/tasks/{task_id}` | タスク削除 |
| GET | `/healthz` | ヘルスチェック |

## ブラウザから試す

Swagger UI には各エンドポイントの入出力例が組み込まれています。下の
スクリーンショットは `POST /tasks` を展開した状態で、リクエストボディの
スキーマ、サンプルペイロード、レスポンスコードが見えます。

![Swagger UI で展開した POST /tasks](../images/todo-api-swagger-post-tasks.png)

1. エンドポイント行をクリックして展開します。
2. **Try it out** を押し、リクエストボディを編集して **Execute** を押します。
3. "Server response" 欄にステータスコード・ボディ・ヘッダーが表示されます。

`POST /tasks` に `{"title": "buy milk", "description": "whole milk, 1 liter"}`
を送ると、`201 Created` と永続化されたタスクが返ります。

![POST /tasks の 201 レスポンス](../images/todo-api-swagger-create-response.png)

## curl での等価操作

Swagger UI には同等の `curl` コマンドも併記されるため、UI 操作と以下の
コマンドは完全に同じ結果になります。

```bash
# 1. 作成
curl -X POST http://localhost:8080/tasks \
  -H 'content-type: application/json' \
  -d '{"title":"buy milk","description":"whole milk, 1 liter"}'

# 2. 一覧
curl http://localhost:8080/tasks

# 3. 更新（<id> は手順 1 で返った id に置き換え）
curl -X PATCH http://localhost:8080/tasks/<id> \
  -H 'content-type: application/json' \
  -d '{"status":"IN_PROGRESS"}'

# 4. 完了
curl -X POST http://localhost:8080/tasks/<id>/complete

# 5. 削除
curl -X DELETE http://localhost:8080/tasks/<id>
```

## レスポンス形式

`TaskResponse` は Pydantic モデルから自動生成されており、Swagger UI のペー
ジ下部に表示されます。各タスクは UUID `id`、`title` / `description`、
ステータス値 (`TODO` / `IN_PROGRESS` / `DONE`)、タイムスタンプを持ちます。

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "buy milk",
  "description": "whole milk, 1 liter",
  "status": "TODO",
  "created_at": "2026-05-14T06:03:22.642785Z",
  "updated_at": "2026-05-14T06:03:22.642805Z"
}
```
