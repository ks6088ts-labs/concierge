---
title: Chat REST API リファレンス
description: クリーンアーキテクチャ Chat FastAPI アプリのエンドポイント
---

## API サーバを起動する

```bash
uv run chat-web
```

## エンドポイント一覧

| Method | Path | 説明 |
|---|---|---|
| POST | `/conversations` | 会話作成 |
| GET | `/conversations` | 会話一覧 |
| GET | `/conversations/{conversation_id}` | 会話取得 |
| DELETE | `/conversations/{conversation_id}` | 会話削除 |
| POST | `/conversations/{conversation_id}/participants` | 参加者追加 |
| POST | `/conversations/{conversation_id}/messages` | メッセージ投稿 |
| GET | `/conversations/{conversation_id}/messages` | メッセージ一覧 |
| GET | `/healthz` | ヘルスチェック |
| GET | `/` | 静的 HTML フロント |

## curl 例

```bash
USER_ID=$(python -c 'import uuid; print(uuid.uuid4())')

curl -X POST http://localhost:8080/conversations \
  -H "X-User-Id: ${USER_ID}" \
  -H 'content-type: application/json' \
  -d '{"title":"general","display_name":"alice"}'
```
