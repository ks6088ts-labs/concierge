"""Settings for the Chat application."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatRepositoryBackend(str, Enum):
    MEMORY = "memory"
    POSTGRES = "postgres"
    AZURE_POSTGRES = "azure-postgres"


class ChatResponderBackend(str, Enum):
    FOUNDRY = "foundry"
    AGENT = "agent"


class ChatSettings(BaseSettings):
    repository_backend: ChatRepositoryBackend = ChatRepositoryBackend.MEMORY
    conversations_table_name: str = "chat_conversations"
    participants_table_name: str = "chat_participants"
    messages_table_name: str = "chat_messages"

    bot_participant_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    bot_display_name: str = "Concierge AI"
    bot_history_limit: int = 20
    bot_system_prompt: str = "あなたは Concierge Chat のアシスタントです。日本語で簡潔に応答してください。"
    bot_model: str = "azure_ai:gpt-5"

    responder_backend: ChatResponderBackend = ChatResponderBackend.FOUNDRY
    # Used when CHAT_RESPONDER_BACKEND=agent (e.g. echo, langgraph-echo, github-copilot-echo).
    bot_agent_type: str = "langgraph-echo"

    realtime_model: str = "gpt-realtime-1.5"
    realtime_voice: str = "alloy"
    realtime_locale: str = "ja-JP"
    realtime_system_prompt: str = "あなたは Concierge Chat のアシスタントです。日本語で簡潔に応答してください。"
    realtime_audio_sample_rate_hz: int = 24000
    realtime_max_session_seconds: int = 600
    # Optional Azure deployment name used for input-audio transcription. When
    # empty (default), the ``transcription`` block is omitted from
    # ``session.update`` and Foundry will not transcribe the user's audio
    # (assistant speech still works). The default OpenAI model id
    # ``gpt-4o-mini-transcribe`` does not correspond to an Azure deployment in
    # most resources, so leaving this empty avoids silent failures.
    realtime_transcription_model: str = ""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="CHAT_",
        extra="ignore",
    )


@lru_cache
def get_chat_settings() -> ChatSettings:
    return ChatSettings()
