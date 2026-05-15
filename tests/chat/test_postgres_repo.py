"""Tests for SqlAlchemy chat repositories."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.persistence.postgres import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)


def _participant(name: str = "alice") -> Participant:
    return Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name=name)


def _make_sqlite_repos() -> tuple[SqlAlchemyConversationRepository, SqlAlchemyMessageRepository]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    conversation_repo = SqlAlchemyConversationRepository(engine, "chat_conversations", "chat_participants")
    message_repo = SqlAlchemyMessageRepository(engine, "chat_messages", "chat_conversations")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    id TEXT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS chat_participants (
                    conversation_id TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    kind VARCHAR(16) NOT NULL,
                    display_name VARCHAR(100) NOT NULL,
                    PRIMARY KEY (conversation_id, participant_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_kind VARCHAR(16) NOT NULL,
                    sender_display_name VARCHAR(100) NOT NULL,
                    role VARCHAR(16) NOT NULL,
                    content VARCHAR(4000) NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
    return conversation_repo, message_repo


class TestSqliteUnit:
    def test_invalid_table_name_raises(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with pytest.raises(ValueError, match="Invalid SQL table name"):
            SqlAlchemyConversationRepository(engine, "chat_conversations;DROP TABLE users;", "chat_participants")

    def test_crud(self) -> None:
        conversation_repo, message_repo = _make_sqlite_repos()
        participant = _participant()
        conversation = Conversation(title="general", participants=[participant])
        conversation_repo.save(conversation)
        message = Message(conversation_id=conversation.id, sender=participant, content="hello")
        message_repo.save(message)

        found = conversation_repo.find_by_id(conversation.id)
        assert found is not None
        assert len(found.participants) == 1
        assert message_repo.find_by_conversation(conversation.id)[0].content == "hello"

        assert message_repo.delete_by_conversation(conversation.id) == 1
        assert conversation_repo.delete(conversation.id) is True


class TestFactoryUnit:
    def test_memory_backend_returns_in_memory_repo(self, monkeypatch) -> None:
        # Explicitly set to ``memory`` so the test is independent of any value
        # configured in the local ``.env`` file (pydantic-settings reads ``.env``
        # even after ``monkeypatch.delenv``).
        monkeypatch.setenv("CHAT_REPOSITORY_BACKEND", "memory")

        from concierge.chat.infrastructure.persistence import factory
        from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository
        from concierge.settings import get_chat_settings

        get_chat_settings.cache_clear()
        factory._get_memory_conversation_repository.cache_clear()

        repo = factory.get_conversation_repository()
        assert isinstance(repo, InMemoryConversationRepository)

    def test_azure_entra_credential_path(self, monkeypatch) -> None:
        monkeypatch.setenv("AZURE_USE_ENTRA_AUTH", "true")
        monkeypatch.setenv("AZURE_DBUSER", "myuser")
        monkeypatch.setenv("AZURE_DBHOST", "myhost.postgres.database.azure.com")
        monkeypatch.setenv("AZURE_DBNAME", "mydb")

        fake_token = MagicMock()
        fake_token.token = "fake-entra-token"

        with patch("azure.identity.DefaultAzureCredential") as mock_credential:
            mock_credential.return_value.get_token.return_value = fake_token
            from concierge.chat.infrastructure.persistence.factory import _resolve_azure_credentials
            from concierge.settings import get_azure_postgres_settings

            get_azure_postgres_settings.cache_clear()
            user, password = _resolve_azure_credentials()

        assert user == "myuser"
        assert password == "fake-entra-token"


def _pg_container_repos():
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("pgvector/pgvector:pg18")
    container.start()
    url = container.get_connection_url().replace("psycopg2", "psycopg")
    engine = create_engine(url, pool_pre_ping=True)
    conversation_repo = SqlAlchemyConversationRepository(engine, "chat_conversations", "chat_participants")
    message_repo = SqlAlchemyMessageRepository(engine, "chat_messages", "chat_conversations")
    conversation_repo.init_schema()
    message_repo.init_schema()
    return conversation_repo, message_repo, container


@pytest.fixture(scope="module")
def pg_repos():
    from tests.conftest import skip_if_docker_unavailable

    skip_if_docker_unavailable()
    conversation_repo, message_repo, container = _pg_container_repos()
    yield conversation_repo, message_repo
    container.stop()


@pytest.mark.integration
class TestIntegration:
    def test_ping(self, pg_repos) -> None:
        conversation_repo, _ = pg_repos
        conversation_repo.ping()

    def test_postgres_crud(self, pg_repos) -> None:
        conversation_repo, message_repo = pg_repos
        participant = _participant()
        conversation = Conversation(title="general", participants=[participant])
        conversation_repo.save(conversation)
        message_repo.save(Message(conversation_id=conversation.id, sender=participant, content="hello"))

        assert conversation_repo.find_by_id(conversation.id) is not None
        assert message_repo.find_by_conversation(conversation.id)
