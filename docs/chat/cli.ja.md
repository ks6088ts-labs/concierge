---
title: Chat CLI リファレンス
description: クリーンアーキテクチャ Chat アプリの Typer コマンド
---

`chat-cli` は Chat アプリの Typer エントリポイントです。同じユースケースを `chat-web` も呼び出すので、両者は `concierge.settings.ChatSettings` を共有します。

```bash
uv run chat-cli --help
```

トップレベル構造：

```text
chat-cli
├── conversation     # create / list / get / delete
├── message          # post / list / reply
└── db               # init / ping / drop  （postgres / azure-postgres 専用）
```

## observability のグローバルオプション

`chat-cli` でも共通トグルを利用できます。

- `--tracing`: Foundry/Azure Monitor tracing を有効化（tracer 名: `concierge-chat`）
- `--mlflow`: `mlflow.langchain.autolog()` を有効化
- `--verbose`: ローカルログを `DEBUG` に設定

!!! warning "`memory` バックエンドはプロセスごとに独立"
    `uv run chat-cli ...` は毎回新しい Python プロセスを起動するため、`memory` バックエンドのストアは毎回空からやり直しです。`create` → `post` のような複数ステップを CLI で行うときは `postgres` バックエンドに切り替えてください（`chat-cli db init` を一度実行）。

## コマンドリファレンス

### `conversation create`

新しい会話を作成し JSON を出力します。

```bash
uv run chat-cli conversation create --title "general" --display-name "alice"
# → {"id": "...", "title": "general", "participants": [...], ...}
```

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--title` | はい | — | 会話タイトル（1〜200 文字） |
| `--display-name` | いいえ | `user-<short-uuid>` | 他参加者に見える表示名 |
| `--user-id` | いいえ | コール毎に新しい UUID。または `$CHAT_USER_ID` | 送信者の UUID |

### `conversation list`

会話一覧を表示。`--mine` を付けるとユーザが参加している会話に絞ります。

```bash
uv run chat-cli conversation list
uv run chat-cli conversation list --mine
uv run chat-cli conversation list --mine --user-id "$CHAT_USER_ID"
```

### `conversation get`

```bash
uv run chat-cli conversation get <conversation_id>
```

### `conversation delete`

会話と関連メッセージを削除。成功時は `deleted` を出力します。

```bash
uv run chat-cli conversation delete <conversation_id>
```

### `message post`

会話に参加（冪等）したうえでユーザメッセージを投稿。作成されたメッセージを JSON で出力します。

```bash
uv run chat-cli message post <conversation_id> \
  --content "こんにちは" --display-name "alice"
```

### `message list`

```bash
uv run chat-cli message list <conversation_id> --limit 100
uv run chat-cli message list <conversation_id> --before "2026-05-16T02:00:00+00:00"
```

### `message reply`

AI エージェント応答をストリーミング表示し、最後に永続化された `AGENT` メッセージを JSON で出力します。`AZURE_AI_PROJECT_ENDPOINT` 設定済みが必須。レスポンダ未設定または会話 ID が存在しないときは終了コード `1`。設定手順は [AI チャットボット応答（任意）](index.ja.md#ai) を参照。

```bash
uv run chat-cli message reply <conversation_id>
# 部分トークンが逐次出力され、最後に改行して:
# {"id": "...", "role": "AGENT", "content": "...", ...}
# 未設定 → "Chatbot is not configured" （exit 1）
```

### `db`（SQL バックエンド専用）

`CHAT_REPOSITORY_BACKEND=memory` の場合は分かりやすいメッセージで失敗します。

```bash
uv run chat-cli db ping        # → Connection OK.
uv run chat-cli db init        # → Database schema initialised successfully.
uv run chat-cli db drop --yes  # 破壊的
```

## ウォークスルー（`postgres` バックエンド） { #postgres- }

CLI 体験としてはこれが一番スムーズです。すべての呼び出しが同じ SQL ストアを共有します。

```bash
# 0. 初回セットアップ
docker compose up -d postgres
echo "CHAT_REPOSITORY_BACKEND=postgres" >> .env
uv run chat-cli db ping
uv run chat-cli db init

# 1. 全コマンドで同じ送信者として動くようユーザ ID を固定
export CHAT_USER_ID=$(python -c 'import uuid; print(uuid.uuid4())')

# 2. 会話を作成して ID を取得
CONV_ID=$(uv run chat-cli conversation create --title "general" --display-name "alice" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "CONV_ID=$CONV_ID"

# 3. 投稿と取得
uv run chat-cli message post "$CONV_ID" --content "こんにちは" --display-name "alice"
uv run chat-cli message list "$CONV_ID"

# 4. （任意）AI 応答を要求（`AZURE_AI_PROJECT_ENDPOINT` 設定済みが必要）
uv run chat-cli message reply "$CONV_ID"
uv run chat-cli message list "$CONV_ID"

# 5. 後片付け
uv run chat-cli conversation delete "$CONV_ID"
```

合格条件：

- 手順 2・3 が想定フィールドを含む JSON を返す
- 手順 3 の `message list` に直前の投稿が含まれる
- 手順 5 で `deleted` が表示され、再度 `conversation get "$CONV_ID"` を打つと `1` で終了し `Conversation not found` が出る

## 環境変数

| 変数 | デフォルト | 型 | 説明 |
|---|---|---|---|
| `CHAT_REPOSITORY_BACKEND` | `memory` | `ChatRepositoryBackend` 列挙型 | 永続化バックエンド |
| `CHAT_CONVERSATIONS_TABLE_NAME` | `chat_conversations` | 文字列 | 会話テーブル名オーバーライド |
| `CHAT_PARTICIPANTS_TABLE_NAME` | `chat_participants` | 文字列 | 参加者テーブル名オーバーライド |
| `CHAT_MESSAGES_TABLE_NAME` | `chat_messages` | 文字列 | メッセージテーブル名オーバーライド |
| `CHAT_USER_ID` | 未設定 | UUID 文字列 | CLI 既定の送信者 ID |
| `CHAT_BOT_MODEL` | `azure_ai:gpt-5` | 文字列 | `init_chat_model` に渡すモデル識別子 |
| `CHAT_BOT_SYSTEM_PROMPT` | 日本語の既定プロンプト | 文字列 | レスポンダが使うシステムメッセージ |
| `CHAT_BOT_DISPLAY_NAME` | `Concierge AI` | 文字列 | ボット参加者の表示名 |
| `CHAT_BOT_PARTICIPANT_ID` | `00000000-0000-0000-0000-000000000001` | UUID | ボット参加者の固定 ID |
| `CHAT_BOT_HISTORY_LIMIT` | `20` | int | モデルに渡すコンテキストの最大件数 |
| `AZURE_AI_PROJECT_ENDPOINT` | 未設定 | URL 文字列 | Foundry レスポンダ有効化に必須（未設定のとき `message reply` は終了コード 1） |
