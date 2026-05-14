from __future__ import annotations

from functools import lru_cache

from concierge.chat.application.repositories import ConversationRepository, MessageRepository
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository
from concierge.settings import ChatRepositoryBackend, get_chat_settings


@lru_cache(maxsize=1)
def _get_memory_conversation_repository() -> InMemoryConversationRepository:
    return InMemoryConversationRepository()


@lru_cache(maxsize=1)
def _get_memory_message_repository() -> InMemoryMessageRepository:
    return InMemoryMessageRepository()


def _build_postgres_engine():
    from sqlalchemy import create_engine

    from concierge.settings import get_postgres_settings

    return create_engine(get_postgres_settings().connection_string, pool_pre_ping=True)


def _resolve_azure_credentials() -> tuple[str, str]:
    from concierge.settings import get_azure_postgres_settings

    settings = get_azure_postgres_settings()
    if settings.use_entra_auth:
        from azure.identity import DefaultAzureCredential

        token = DefaultAzureCredential().get_token(settings.entra_token_scope)
        if not settings.dbuser:
            raise ValueError(
                "AZURE_DBUSER must be set to the Entra principal name (or PostgreSQL role) "
                "when AZURE_USE_ENTRA_AUTH=true."
            )
        return settings.dbuser, token.token
    if not (settings.dbuser and settings.dbpassword):
        raise ValueError("AZURE_DBUSER and AZURE_DBPASSWORD must be set when AZURE_USE_ENTRA_AUTH=false.")
    return settings.dbuser, settings.dbpassword


def _build_azure_postgres_engine():
    from sqlalchemy import create_engine

    from concierge.settings import get_azure_postgres_settings

    settings = get_azure_postgres_settings()
    if not settings.dbhost or not settings.dbname:
        raise ValueError("AZURE_DBHOST and AZURE_DBNAME must be set.")
    user, password = _resolve_azure_credentials()
    return create_engine(settings.build_connection_string(password=password, user=user), pool_pre_ping=True)


@lru_cache(maxsize=2)
def _get_cached_engine(backend: ChatRepositoryBackend):
    if backend is ChatRepositoryBackend.POSTGRES:
        return _build_postgres_engine()
    if backend is ChatRepositoryBackend.AZURE_POSTGRES:
        return _build_azure_postgres_engine()
    raise ValueError(f"Unknown backend: {backend!r}")  # pragma: no cover


def get_conversation_repository() -> ConversationRepository:
    settings = get_chat_settings()
    backend = settings.repository_backend
    if backend is ChatRepositoryBackend.MEMORY:
        return _get_memory_conversation_repository()
    if backend in (ChatRepositoryBackend.POSTGRES, ChatRepositoryBackend.AZURE_POSTGRES):
        from concierge.chat.infrastructure.persistence.postgres import SqlAlchemyConversationRepository

        return SqlAlchemyConversationRepository(
            _get_cached_engine(backend),
            conversations_table_name=settings.conversations_table_name,
            participants_table_name=settings.participants_table_name,
        )
    raise ValueError(f"Unhandled ChatRepositoryBackend value: {backend!r}")  # pragma: no cover


def get_message_repository() -> MessageRepository:
    settings = get_chat_settings()
    backend = settings.repository_backend
    if backend is ChatRepositoryBackend.MEMORY:
        return _get_memory_message_repository()
    if backend in (ChatRepositoryBackend.POSTGRES, ChatRepositoryBackend.AZURE_POSTGRES):
        from concierge.chat.infrastructure.persistence.postgres import SqlAlchemyMessageRepository

        return SqlAlchemyMessageRepository(
            _get_cached_engine(backend),
            messages_table_name=settings.messages_table_name,
            conversations_table_name=settings.conversations_table_name,
        )
    raise ValueError(f"Unhandled ChatRepositoryBackend value: {backend!r}")  # pragma: no cover
