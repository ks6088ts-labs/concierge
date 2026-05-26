---
title: Chat CLI Reference
description: Typer commands for the clean architecture Chat app
---

`chat-cli` is the Typer entry point for the Chat app. The same use cases are
exposed by `chat-web`; both share the same configuration via
`concierge.settings.ChatSettings`.

```bash
uv run chat-cli --help
```

Top-level structure:

```text
chat-cli
├── conversation     # create / list / get / delete
├── message          # post / list / reply
├── realtime         # status
└── db               # init / ping / drop  (postgres / azure-postgres only)
```

## Global observability options

`chat-cli` supports the same global toggles as the tutorial CLIs:

- `--tracing` enables Foundry/Azure Monitor tracing (`concierge-chat` tracer name).
- `--mlflow` enables `mlflow.langchain.autolog()`.
- `--verbose` sets local logging to `DEBUG`.

!!! warning "The `memory` backend is per-process"
    Every `uv run chat-cli ...` invocation starts a fresh interpreter, so
    the in-memory store is empty again. For two-step flows (create →
    post) switch to the `postgres` backend (`chat-cli db init` once).

## Command reference

### `conversation create`

Creates a new conversation and outputs JSON.

```bash
uv run chat-cli conversation create --title "general" --display-name "alice"
# → {"id": "...", "title": "general", "participants": [...], ...}
```

| Option | Required | Default | Description |
|---|---|---|---|
| `--title` | yes | — | Conversation title (1-200 chars) |
| `--display-name` | no | `user-<short-uuid>` | Display name shown to other participants |
| `--user-id` | no | new UUID per call, or `$CHAT_USER_ID` | Sender UUID |

### `conversation list`

Lists conversations. By default shows everything; `--mine` filters to those
where the resolved user is a participant.

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

Deletes the conversation and its messages. Prints `deleted` on success.

```bash
uv run chat-cli conversation delete <conversation_id>
```

### `message post`

Joins the conversation (idempotent) and posts a user message. Prints the
created message as JSON.

```bash
uv run chat-cli message post <conversation_id> \
  --content "hello" --display-name "alice"
```

### `message list`

```bash
uv run chat-cli message list <conversation_id> --limit 100
uv run chat-cli message list <conversation_id> --before "2026-05-16T02:00:00+00:00"
```

### `message reply`

Streams an AI agent reply to stdout as it is generated, then prints the
persisted `AGENT` message as JSON on the final line. Requires
`AZURE_AI_PROJECT_ENDPOINT` to be set. Exits with code `1` when the
responder is not configured or the conversation is not found. See
[AI chatbot replies (optional)](index.md#ai-chatbot-replies-optional).

```bash
uv run chat-cli message reply <conversation_id>
# streams partial tokens to stdout… then on a new line:
# {"id": "...", "role": "AGENT", "content": "...", ...}
# unconfigured → "Chatbot is not configured" (exit 1)
```

### `db` (SQL backends only)

These commands fail fast with a clear message when
`CHAT_REPOSITORY_BACKEND=memory`.

```bash
uv run chat-cli db ping        # → Connection OK.
uv run chat-cli db init        # → Database schema initialised successfully.
uv run chat-cli db drop --yes  # destructive
```

### `realtime status` { #realtime-status }

Non-interactive sanity check for the realtime voice configuration. Reads
`AZURE_AI_PROJECT_ENDPOINT_REALTIME`, `CHAT_REALTIME_MODEL`, and
`CHAT_REALTIME_VOICE` and reports whether realtime voice is enabled. **No
live WebSocket connection is made**, so this is safe to run from CI.

```bash
uv run chat-cli realtime status
```

Example output (configured):

```text
AZURE_AI_PROJECT_ENDPOINT_REALTIME : https://myresource.openai.azure.com/
CHAT_REALTIME_MODEL               : gpt-realtime-1.5
CHAT_REALTIME_VOICE               : alloy
導出 WSS ホスト                   : wss://myre****azure.com/openai/v1/realtime
ステータス: ✅ 設定済み
```

Example output (not configured):

```text
AZURE_AI_PROJECT_ENDPOINT_REALTIME : (未設定)
CHAT_REALTIME_MODEL               : gpt-realtime-1.5
CHAT_REALTIME_VOICE               : alloy
ステータス: ❌ 未設定 — リアルタイム機能は無効です
```

Exit code is `1` when not configured, `0` otherwise. See
[Realtime voice (optional)](index.md#realtime-voice-optional) for the full
feature reference.

## Full walkthrough (with the `postgres` backend)

This is the smoothest CLI experience: a single SQL store backs every
invocation.

```bash
# 0. One-time setup.
docker compose up -d postgres
echo "CHAT_REPOSITORY_BACKEND=postgres" >> .env
uv run chat-cli db ping
uv run chat-cli db init

# 1. Pin a user identity so every command speaks as the same person.
export CHAT_USER_ID=$(python -c 'import uuid; print(uuid.uuid4())')

# 2. Create a conversation; capture the id.
CONV_ID=$(uv run chat-cli conversation create --title "general" --display-name "alice" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "CONV_ID=$CONV_ID"

# 3. Post and read.
uv run chat-cli message post "$CONV_ID" --content "hello" --display-name "alice"
uv run chat-cli message list "$CONV_ID"

# 4. (Optional) Trigger an AI reply (requires AZURE_AI_PROJECT_ENDPOINT).
uv run chat-cli message reply "$CONV_ID"
uv run chat-cli message list "$CONV_ID"

# 5. Clean up.
uv run chat-cli conversation delete "$CONV_ID"
```

Pass criteria:

- Steps 2 and 3 print JSON with the expected fields.
- Step 3's `message list` includes the message posted in the same step.
- Step 5 prints `deleted` and `conversation get "$CONV_ID"` then exits with
  `1` and `Conversation not found`.

## Environment variables

| Variable | Default | Type | Description |
|---|---|---|---|
| `CHAT_REPOSITORY_BACKEND` | `memory` | `ChatRepositoryBackend` enum | Persistence backend |
| `CHAT_CONVERSATIONS_TABLE_NAME` | `chat_conversations` | string | Conversations table override |
| `CHAT_PARTICIPANTS_TABLE_NAME` | `chat_participants` | string | Participants table override |
| `CHAT_MESSAGES_TABLE_NAME` | `chat_messages` | string | Messages table override |
| `CHAT_USER_ID` | unset | UUID string | Default sender id used by `chat-cli` |
| `CHAT_BOT_MODEL` | `azure_ai:gpt-5` | string | Model id passed to `init_chat_model` |
| `CHAT_BOT_SYSTEM_PROMPT` | Japanese default prompt | string | System message used by the responder |
| `CHAT_BOT_DISPLAY_NAME` | `Concierge AI` | string | Display name for the bot participant |
| `CHAT_BOT_PARTICIPANT_ID` | `00000000-0000-0000-0000-000000000001` | UUID | Stable id for the bot participant |
| `CHAT_BOT_HISTORY_LIMIT` | `20` | int | Maximum context messages forwarded to the model |
| `CHAT_BOT_AGENT_TYPE` | `foundry` | string | Responder selector: `foundry` (default, streaming) or a registered agent type (`echo`, `langgraph`, `github-copilot-sdk`, `microsoft-agent-framework`) |
| `AZURE_AI_PROJECT_ENDPOINT` | unset | URL string | Required to enable the Foundry responder (otherwise `message reply` exits with code 1) |
| `AZURE_AI_PROJECT_ENDPOINT_REALTIME` | unset | URL string | Required to enable realtime voice. Accepts both `https://<r>.openai.azure.com/` and `https://<r>.services.ai.azure.com/` (auto-normalised). `realtime status` exits with code 1 when empty. |
| `CHAT_REALTIME_MODEL` | `gpt-realtime-1.5` | string | Realtime model deployment name |
| `CHAT_REALTIME_VOICE` | `alloy` | string | Voice id: `alloy` / `ash` / `ballad` / `coral` / `echo` / `sage` / `shimmer` / `verse` |
| `CHAT_REALTIME_LOCALE` | `ja-JP` | string | Transcription locale. BCP-47 values like `ja-JP` are reduced to the ISO-639-1 primary subtag (`ja`) when forwarded to Foundry. |
| `CHAT_REALTIME_SYSTEM_PROMPT` | Japanese default prompt | string | System message used by the realtime session |
| `CHAT_REALTIME_AUDIO_SAMPLE_RATE_HZ` | `24000` | int | PCM16 sample rate (Foundry fixed value) |
| `CHAT_REALTIME_MAX_SESSION_SECONDS` | `600` | int | Server-side session timeout in seconds |
| `CHAT_REALTIME_TRANSCRIPTION_MODEL` | `""` | string | Azure deployment name for input-audio transcription. When empty the `transcription` block is omitted from `session.update`. |
