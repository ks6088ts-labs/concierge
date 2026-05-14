"""Settings for the Chat application."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatRepositoryBackend(str, Enum):
    MEMORY = "memory"
    POSTGRES = "postgres"
    AZURE_POSTGRES = "azure-postgres"


class ChatSettings(BaseSettings):
    repository_backend: ChatRepositoryBackend = ChatRepositoryBackend.MEMORY
    conversations_table_name: str = "chat_conversations"
    participants_table_name: str = "chat_participants"
    messages_table_name: str = "chat_messages"

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
