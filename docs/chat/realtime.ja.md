---
title: リアルタイム音声会話
description: Foundry GPT Realtime API を使った WebSocket ベースのリアルタイム音声会話機能
---

## 概要

リアルタイム音声会話機能は、ブラウザと Microsoft Foundry の GPT Realtime API を
**WebSocket バックエンドプロキシ**でつなぎます。音声処理はすべてサーバ側で行われ、
Foundry の資格情報はサーバ外に出ません。

```
ブラウザ ⇄ FastAPI (chat-web) ⇄ Foundry /openai/v1/realtime
```

ユーザーと AI エージェントの音声テキスト (transcript) は通常の `Message` として
テキストチャットと同じストアに保存されるため、`/conversations/{id}/messages` で
一覧できます。

---

## クイックスタート

```bash
# 1. .env にリアルタイム用エンドポイントを設定（詳細は「設定」セクション参照）。
echo "AZURE_AI_PROJECT_ENDPOINT_REALTIME=https://<resource>.openai.azure.com/" >> .env

# 2. 設定が読み込めるか確認（実際の接続は行わない）。
uv run chat-cli realtime status
# → ステータス: ✅ 設定済み

# 3. API サーバを起動。
uv run chat-web
```

Chromium 系か Firefox 系ブラウザで <http://localhost:8080/realtime> を開き、
サイドバーで会話を作成 → ツールバーの **通話開始** をクリックして話します。
初回はマイクの利用許可ダイアログが表示されます。

> **メモ** — テキストチャットはリアルタイム用エンドポイントを必要としません。
> `AZURE_AI_PROJECT_ENDPOINT_REALTIME` 未設定で失敗するのはリアルタイム
> WebSocket だけ（クローズコード `4503`）です。

---

## Web UI の使い方

同梱のフロントエンドは <http://localhost:8080/realtime>
（実体は [`concierge/chat/infrastructure/web/static_realtime/index.html`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/chat/infrastructure/web/static_realtime/index.html)）
にあり、ビルド不要の単一 HTML です。

### 画面構成

| 領域 | 機能 |
|---|---|
| サイドバー：**表示名 / ユーザー ID** | `display_name` と `user_id` (UUID) を `localStorage` (`chat_rt_display_name`, `chat_rt_user_id`) に保存。UUID は初回ロード時に自動生成され、`X-User-Id` ヘッダと `?user_id=` クエリの両方に使われる |
| サイドバー：**＋ 新しい会話** | `POST /conversations` を呼んで一覧を更新 |
| サイドバー：会話リスト | `GET /conversations` の結果を表示。クリックで `GET /conversations/{id}/messages` を呼び履歴をロード |
| サイドバー：会話の **🗑 削除ボタン** | 各会話の行にホバー（または選択中）で表示。確認モーダルで「削除する」を選ぶと `DELETE /conversations/{id}` を呼び会話とメッセージを完全削除する。表示中の会話を削除した場合は通話を終了して履歴ビューもクリアする |
| ツールバー：**通話開始 / 通話終了** | リアルタイム WebSocket を開始 / 終了。会話を選択するまで無効。通話中は赤いボタンになる |
| ツールバー：ステータス表示 | 接続 / セッション状態（例：`通話中 🔴`、クローズコードに対応した日本語ラベル） |
| メッセージ一覧 | ユーザー / AI の transcript を吹き出し表示。`concierge.message.persisted` を受信するたび追記 |
| 仮文字起こし行 | AI 側の部分 transcript（`response.audio_transcript.delta`）をリアルタイム表示。確定時に消える |

### ブラウザ → サーバのデータフロー

1. `getUserMedia({ audio: true })` でマイク権限をリクエスト。
2. `AudioWorklet` で 24 kHz モノラル PCM16（`CHAT_REALTIME_AUDIO_SAMPLE_RATE_HZ` の値）に変換し、200 ms 単位で分割。
3. 各チャンクを base64 エンコードし、`{"type":"oai-event","payload":{"type":"input_audio_buffer.append","audio":"<b64>"}}` として送信。
4. Foundry が返す `response.audio.delta` イベントを PCM16 にデコードし、キュー付き `AudioBufferSource` で順次再生。

### 対応ブラウザ

`AudioWorklet` / `WebSocket` / `MediaDevices.getUserMedia` / `crypto.randomUUID`
を利用しています。最近の Chrome、Edge、Firefox、Safari で動作します。Safari は
セキュリティ仕様上、`AudioContext` の音声出力にユーザー操作（**通話開始**
ボタンのクリック）が必要です。

### UI に現れるエラー

| 症状 | 原因 | 対処 |
|---|---|---|
| 赤バナー：`マイクへのアクセスが拒否されました` | ブラウザがマイクをブロック | ブラウザ設定で `localhost:8080` のマイクを許可 |
| ステータス：`リアルタイム機能が未設定です` | WebSocket が `4503` で切断 | `AZURE_AI_PROJECT_ENDPOINT_REALTIME` を設定し `chat-web` を再起動 |
| ステータス：`会話が見つかりません` | WebSocket が `4404` で切断 | 会話を再選択するか作り直す |
| ステータス：`不正なリクエスト` | WebSocket が `4400` で切断 | `localStorage` を削除してユーザー UUID を再生成 |

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
| `CHAT_REALTIME_LOCALE` | `ja-JP` | 文字起こし言語。Foundry GA は ISO 639-1（`ja`、`en` など）を要求するため、`ja-JP` のような BCP-47 形式は自動的に主言語サブタグへ変換されます |
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
導出 WSS ホスト                   : wss://myre****azure.com/openai/v1/realtime
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
