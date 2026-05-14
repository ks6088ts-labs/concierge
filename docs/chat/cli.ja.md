---
title: Chat CLI リファレンス
description: クリーンアーキテクチャ Chat アプリの Typer コマンド
---

## コマンド

```bash
uv run chat-cli conversation create --title "general" --display-name "alice"
uv run chat-cli conversation list --mine
uv run chat-cli conversation get <conversation_id>
uv run chat-cli conversation delete <conversation_id>
uv run chat-cli message post <conversation_id> --content "こんにちは" --display-name "alice"
uv run chat-cli message list <conversation_id> --limit 100
```

## データベースコマンド

```bash
uv run chat-cli db init
uv run chat-cli db ping
uv run chat-cli db drop --yes
```

## 環境変数

| 変数 | デフォルト | 型 | 説明 |
|---|---|---|---|
| `CHAT_REPOSITORY_BACKEND` | `memory` | `ChatRepositoryBackend` 列挙型 | 永続化バックエンド |
| `CHAT_CONVERSATIONS_TABLE_NAME` | `chat_conversations` | 文字列 | 会話テーブル名オーバーライド |
| `CHAT_PARTICIPANTS_TABLE_NAME` | `chat_participants` | 文字列 | 参加者テーブル名オーバーライド |
| `CHAT_MESSAGES_TABLE_NAME` | `chat_messages` | 文字列 | メッセージテーブル名オーバーライド |
| `CHAT_USER_ID` | 未設定 | UUID 文字列 | CLI 既定の送信者 ID |
