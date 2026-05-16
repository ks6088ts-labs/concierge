---
title: Realtime Voice Chat
description: WebSocket-based realtime voice conversation using Foundry GPT Realtime API
---

## Overview

The realtime voice feature adds a **bidirectional WebSocket proxy** between the browser
and Microsoft Foundry's GPT Realtime API. All audio is processed server-side — Foundry
credentials never leave the server.

```
Browser ⇄ FastAPI (chat-web) ⇄ Foundry /openai/realtime
```

Transcripts from both the user and the AI agent are persisted as regular `Message`
objects in the same store as text chat, so they appear in `/conversations/{id}/messages`.

---

## Prerequisites

A Foundry resource in a region that supports the GPT Realtime model (for example
`swedencentral` or `eastus2`). This is typically **different** from the region used
for standard text chat, so a separate endpoint variable is provided.

Reference:
[Use the GPT Realtime API via WebSockets (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-websockets?tabs=ga)

---

## Configuration

### `.env` settings

```dotenv
# Realtime-specific Foundry endpoint (different region from AZURE_AI_PROJECT_ENDPOINT)
AZURE_AI_PROJECT_ENDPOINT_REALTIME=https://<resource>.openai.azure.com/

# Realtime model deployment name
CHAT_REALTIME_MODEL=gpt-realtime-1.5

# Voice: alloy | ash | ballad | coral | echo | sage | shimmer | verse
CHAT_REALTIME_VOICE=alloy

# Language locale for transcription
CHAT_REALTIME_LOCALE=ja-JP

# Max session duration in seconds (server-side timeout)
CHAT_REALTIME_MAX_SESSION_SECONDS=600
```

`AZURE_AI_PROJECT_ENDPOINT_REALTIME` accepts two URL formats:

| Format | Example |
|--------|---------|
| `https://<resource>.openai.azure.com/` | Direct Azure OpenAI endpoint |
| `https://<resource>.services.ai.azure.com/` | Azure AI Services endpoint (normalised automatically) |

When `AZURE_AI_PROJECT_ENDPOINT_REALTIME` is **empty**, the
`/conversations/{id}/realtime` WebSocket closes immediately with code `4503`.
This does **not** affect the text chat functionality.

### Settings reference

All realtime settings use the `CHAT_` prefix.

| Variable | Default | Description |
|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT_REALTIME` | `""` (disabled) | Foundry endpoint for the realtime model |
| `CHAT_REALTIME_MODEL` | `gpt-realtime-1.5` | Realtime model deployment name |
| `CHAT_REALTIME_VOICE` | `alloy` | Voice identifier |
| `CHAT_REALTIME_LOCALE` | `ja-JP` | Transcription language |
| `CHAT_REALTIME_AUDIO_SAMPLE_RATE_HZ` | `24000` | PCM16 sample rate (Foundry fixed value) |
| `CHAT_REALTIME_MAX_SESSION_SECONDS` | `600` | Server-side session timeout |

---

## Pages

| URL | Description |
|-----|-------------|
| `http://localhost:8080/realtime` | Realtime voice chat UI |
| `http://localhost:8080/realtime-static/` | Static file mount |
| `ws://localhost:8080/conversations/{id}/realtime` | WebSocket endpoint |

---

## WebSocket protocol

### Endpoint

```
WS /conversations/{conversation_id}/realtime
   ?user_id=<uuid>
   [&display_name=<string>]
```

### Server → Client events

| `type` | Payload | Notes |
|--------|---------|-------|
| `concierge.session.ready` | `{"conversation_id": "..."}` | First message after accept |
| `oai-event` | `{"payload": <Foundry event JSON>}` | Transparent relay of all Foundry events |
| `concierge.message.persisted` | `{"message": <MessageResponse>}` | USER or AGENT transcript saved |
| `concierge.error` | `{"detail": "..."}` | Unhandled server error |

### Client → Server events

| `type` | Payload | Notes |
|--------|---------|-------|
| `oai-event` | `{"payload": <Foundry event JSON>}` | Forwarded to Foundry |

### Close codes

| Code | Meaning |
|------|---------|
| `4400` | `user_id` is missing or not a valid UUID |
| `4404` | `conversation_id` does not exist |
| `4503` | `AZURE_AI_PROJECT_ENDPOINT_REALTIME` is not configured |
| `1000` | Normal client-initiated close |

---

## CLI status check

```bash
uv run chat-cli realtime status
```

Example output (configured):

```
AZURE_AI_PROJECT_ENDPOINT_REALTIME : https://myresource.openai.azure.com/
CHAT_REALTIME_MODEL               : gpt-realtime-1.5
CHAT_REALTIME_VOICE               : alloy
導出 WSS ホスト                   : wss://myre****azure.com/openai/realtime
ステータス: ✅ 設定済み
```

Example output (not configured):

```
AZURE_AI_PROJECT_ENDPOINT_REALTIME : (未設定)
CHAT_REALTIME_MODEL               : gpt-realtime-1.5
CHAT_REALTIME_VOICE               : alloy
ステータス: ❌ 未設定 — リアルタイム機能は無効です
```

Exit code is `1` when not configured, `0` otherwise.

---

## Troubleshooting

### WebSocket closes with `4503`

`AZURE_AI_PROJECT_ENDPOINT_REALTIME` is not set or empty. Set it in `.env` and restart
`chat-web`.

```bash
echo "AZURE_AI_PROJECT_ENDPOINT_REALTIME=https://<resource>.openai.azure.com/" >> .env
uv run chat-web
```

### WebSocket closes with `4404`

The `conversation_id` in the URL does not exist. Create a conversation first via
`POST /conversations`.

### WebSocket closes with `4400`

The `user_id` query parameter is missing or is not a valid UUID. Generate one with:

```bash
python -c 'import uuid; print(uuid.uuid4())'
```

### Microphone permission denied

The browser blocked microphone access. Check `chrome://settings/content/microphone` or
the browser's site-specific permissions. The UI shows an error banner when this occurs.

### `ClientAuthenticationError` / `DefaultAzureCredential failed`

`FoundryRealtimeResponder` calls `DefaultAzureCredential().get_token(...)`. Ensure your
environment can issue a token — for example via `az login` or a managed identity.
