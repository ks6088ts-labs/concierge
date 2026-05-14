---
title: Todo REST API リファレンス
description: クリーンアーキテクチャ Todo FastAPI アプリのエンドポイント
---

## エンドポイント

| Method | Path | 説明 |
|---|---|---|
| POST | `/tasks` | タスク作成 |
| GET | `/tasks` | タスク一覧 |
| GET | `/tasks/{task_id}` | タスク取得 |
| PATCH | `/tasks/{task_id}` | タスク更新 |
| POST | `/tasks/{task_id}/complete` | タスク完了 |
| DELETE | `/tasks/{task_id}` | タスク削除 |
| GET | `/healthz` | ヘルスチェック |

## 実行例

```bash
curl -X POST http://localhost:8080/tasks -H 'content-type: application/json' -d '{"title":"buy milk"}'
```
