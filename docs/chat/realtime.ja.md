---
title: リアルタイム音声会話
description: Foundry GPT Realtime API を使った WebSocket ベースのリアルタイム音声会話機能
---

## 概要

リアルタイム音声会話機能は、ブラウザと Microsoft Foundry の GPT Realtime API を
**WebSocket バックエンドプロキシ**でつなぎます。音声処理はすべてサーバ側で行われ、
Foundry の資格情報はサーバ外に出ません。

```
ブラウザ ⇄ FastAPI (chat-web) ⇄ Foundry /openai/realtime
```

ユーザーと AI エージェントの音声テキスト (transcript) は通常の `Message` として
テキストチャットと同じストアに保存されるため、`/conversations/{id}/messages` で
一覧できます。

---

## 前提条件

GPT Realtime モデルが利用可能なリージョン (例: `swedencentral`, `eastus2`) の
Foundry リソースが必要です。通常のテキストチャットとは別リージョンになるため、
専用の環境変数が用意されています。

参考:
[GPT Realtime API via WebSockets の使用方法 (Microsoft Learn)](https://learn.microsoft.com/ja-jp/azure/foundry/openai/how-to/realtime-audio-websockets?tabs=ga)

---

## 設定

### `.env` 設定例

```dotenv
# リアルタイム専用 Foundry エンドポイント (AZURE_AI_PROJECT_ENDPOINT とは別リージョン可)
AZURE_AI_PROJECT_ENDPOINT_REALTIME=https://<resource>.openai.azure.com/

# リアルタイムモデルのデプロイ名
CHAT_REALTIME_MODEL=gpt-realtime-1.5

# ボイス: alloy | ash | ballad | coral | echo | sage | shimmer | verse
CHAT_REALTIME_VOICE=alloy

# 文字起こしの言語
CHAT_REALTIME_LOCALE=ja-JP

# サーバ側のセッションタイムアウト (秒)
CHAT_REALTIME_MAX_SESSION_SECONDS=600
```

`AZURE_AI_PROJECT_ENDPOINT_REALTIME` は以下の 2 形式に対応しています。

| 形式 | 例 |
|------|----|
| `https://<resource>.openai.azure.com/` | Azure OpenAI 直接エンドポイント |
| `https://<resource>.services.ai.azure.com/` | Azure AI Services エンドポイント (自動正規化) |

`AZURE_AI_PROJECT_ENDPOINT_REALTIME` が **空** の場合、
`/conversations/{id}/realtime` WebSocket は即座に `4503` で閉じます。
テキストチャット機能には影響しません。

### 設定一覧

すべてのリアルタイム設定は `CHAT_` プレフィックスを使用します。

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `AZURE_AI_PROJECT_ENDPOINT_REALTIME` | `""` (無効) | リアルタイムモデル用 Foundry エンドポイント |
| `CHAT_REALTIME_MODEL` | `gpt-realtime-1.5` | リアルタイムモデルのデプロイ名 |
| `CHAT_REALTIME_VOICE` | `alloy` | ボイス識別子 |
| `CHAT_REALTIME_LOCALE` | `ja-JP` | 文字起こし言語 |
| `CHAT_REALTIME_AUDIO_SAMPLE_RATE_HZ` | `24000` | PCM16 サンプルレート (Foundry 固定値) |
| `CHAT_REALTIME_MAX_SESSION_SECONDS` | `600` | サーバ側セッションタイムアウト |

---

## ページ

| URL | 説明 |
|-----|------|
| `http://localhost:8080/realtime` | リアルタイム音声会話 UI |
| `http://localhost:8080/realtime-static/` | 静的ファイルマウント |
| `ws://localhost:8080/conversations/{id}/realtime` | WebSocket エンドポイント |

---

## WebSocket プロトコル

### エンドポイント

```
WS /conversations/{conversation_id}/realtime
   ?user_id=<uuid>
   [&display_name=<string>]
```

### サーバ → クライアント イベント

| `type` | ペイロード | 備考 |
|--------|-----------|------|
| `concierge.session.ready` | `{"conversation_id": "..."}` | accept 直後の最初のメッセージ |
| `oai-event` | `{"payload": <Foundry イベント JSON>}` | Foundry イベントの透過リレー |
| `concierge.message.persisted` | `{"message": <MessageResponse>}` | USER/AGENT transcript の永続化通知 |
| `concierge.error` | `{"detail": "..."}` | サーバ側の未処理エラー |

### クライアント → サーバ イベント

| `type` | ペイロード | 備考 |
|--------|-----------|------|
| `oai-event` | `{"payload": <Foundry イベント JSON>}` | Foundry への透過転送 |

### クローズコード

| コード | 意味 |
|--------|------|
| `4400` | `user_id` が未指定または UUID として不正 |
| `4404` | `conversation_id` が存在しない |
| `4503` | `AZURE_AI_PROJECT_ENDPOINT_REALTIME` が未設定 |
| `1000` | クライアント側から正常切断 |

---

## CLI ステータス確認

```bash
uv run chat-cli realtime status
```

設定済みの場合の出力例:

```
AZURE_AI_PROJECT_ENDPOINT_REALTIME : https://myresource.openai.azure.com/
CHAT_REALTIME_MODEL               : gpt-realtime-1.5
CHAT_REALTIME_VOICE               : alloy
導出 WSS ホスト                   : wss://myre****azure.com/openai/realtime
ステータス: ✅ 設定済み
```

未設定の場合の出力例:

```
AZURE_AI_PROJECT_ENDPOINT_REALTIME : (未設定)
CHAT_REALTIME_MODEL               : gpt-realtime-1.5
CHAT_REALTIME_VOICE               : alloy
ステータス: ❌ 未設定 — リアルタイム機能は無効です
```

未設定の場合は終了コード `1`、設定済みの場合は `0` です。

---

## トラブルシューティング

### WebSocket が `4503` で閉じる

`AZURE_AI_PROJECT_ENDPOINT_REALTIME` が未設定または空です。`.env` に追記して
`chat-web` を再起動してください。

```bash
echo "AZURE_AI_PROJECT_ENDPOINT_REALTIME=https://<resource>.openai.azure.com/" >> .env
uv run chat-web
```

### WebSocket が `4404` で閉じる

URL の `conversation_id` が存在しません。先に `POST /conversations` で会話を作成してください。

### WebSocket が `4400` で閉じる

`user_id` クエリパラメータが未指定か UUID として不正です。次のコマンドで生成できます。

```bash
python -c 'import uuid; print(uuid.uuid4())'
```

### マイクのアクセス許可が拒否された

ブラウザがマイクへのアクセスをブロックしています。ブラウザの設定でこのサイトの
マイク使用を許可してください。UI にエラーバナーが表示されます。

### `ClientAuthenticationError` / `DefaultAzureCredential failed`

`FoundryRealtimeResponder` は `DefaultAzureCredential().get_token(...)` を使用します。
トークンを発行できる環境 (`az login`、マネージド ID など) であることを確認してください。
