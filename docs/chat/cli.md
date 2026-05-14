---
title: Chat CLI Reference
description: Typer commands for the clean architecture Chat app
---

## Commands

```bash
uv run chat-cli conversation create --title "general" --display-name "alice"
uv run chat-cli conversation list --mine
uv run chat-cli conversation get <conversation_id>
uv run chat-cli conversation delete <conversation_id>
uv run chat-cli message post <conversation_id> --content "hello" --display-name "alice"
uv run chat-cli message list <conversation_id> --limit 100
```

## Database Commands

```bash
uv run chat-cli db init
uv run chat-cli db ping
uv run chat-cli db drop --yes
```

## Environment Variables

| Variable | Default | Type | Description |
|---|---|---|---|
| `CHAT_REPOSITORY_BACKEND` | `memory` | `ChatRepositoryBackend` enum | Persistence backend |
| `CHAT_CONVERSATIONS_TABLE_NAME` | `chat_conversations` | string | Conversations table override |
| `CHAT_PARTICIPANTS_TABLE_NAME` | `chat_participants` | string | Participants table override |
| `CHAT_MESSAGES_TABLE_NAME` | `chat_messages` | string | Messages table override |
| `CHAT_USER_ID` | unset | UUID string | CLI default sender id |
