"""Tests for SqlAlchemyTaskRepository.

Unit tests use a real in-process SQLite database (via SQLAlchemy) so they run
without Docker.  Integration tests (marked ``pytest.mark.integration``) spin up
a real PostgreSQL container with ``testcontainers``.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine

from concierge.todo.domain.entities import Task
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.persistence.postgres import SqlAlchemyTaskRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqlite_repo() -> SqlAlchemyTaskRepository:
    """Return a fresh ``SqlAlchemyTaskRepository`` backed by an in-memory SQLite DB."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    repo = SqlAlchemyTaskRepository(engine, table_name="todo_tasks")
    # SQLite does not support TIMESTAMPTZ, so we rewrite the DDL slightly.
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS todo_tasks (
                    id          TEXT PRIMARY KEY,
                    title       VARCHAR(200)  NOT NULL,
                    description VARCHAR(2000),
                    status      VARCHAR(32)   NOT NULL,
                    created_at  DATETIME      NOT NULL,
                    updated_at  DATETIME      NOT NULL
                )
                """
            )
        )
    return repo


# ---------------------------------------------------------------------------
# Unit tests (SQLite, no Docker)
# ---------------------------------------------------------------------------


class TestSqlAlchemyTaskRepositoryUnit:
    """CRUD and filter tests against an in-memory SQLite database."""

    def test_save_and_find_by_id(self) -> None:
        repo = _make_sqlite_repo()
        task = Task(title="buy milk")
        repo.save(task)
        found = repo.find_by_id(task.id)
        assert found is not None
        assert found.id == task.id
        assert found.title == "buy milk"

    def test_find_by_id_returns_none_for_missing(self) -> None:
        repo = _make_sqlite_repo()
        assert repo.find_by_id(uuid.uuid4()) is None

    def test_find_all_empty(self) -> None:
        repo = _make_sqlite_repo()
        assert repo.find_all() == []

    def test_find_all_returns_all_tasks(self) -> None:
        repo = _make_sqlite_repo()
        repo.save(Task(title="t1"))
        repo.save(Task(title="t2"))
        assert len(repo.find_all()) == 2

    def test_find_all_with_status_filter(self) -> None:
        repo = _make_sqlite_repo()
        repo.save(Task(title="todo"))
        repo.save(Task(title="done", status=TaskStatus.DONE))
        done = repo.find_all(status=TaskStatus.DONE)
        assert len(done) == 1
        assert done[0].status == TaskStatus.DONE

    def test_save_updates_existing_task(self) -> None:
        repo = _make_sqlite_repo()
        task = Task(title="original")
        repo.save(task)
        task.update(title="updated")
        repo.save(task)
        found = repo.find_by_id(task.id)
        assert found is not None
        assert found.title == "updated"

    def test_delete_existing_task(self) -> None:
        repo = _make_sqlite_repo()
        task = Task(title="to delete")
        repo.save(task)
        assert repo.delete(task.id) is True
        assert repo.find_by_id(task.id) is None

    def test_delete_missing_task_returns_false(self) -> None:
        repo = _make_sqlite_repo()
        assert repo.delete(uuid.uuid4()) is False


# ---------------------------------------------------------------------------
# Unit tests for factory / Azure credential path (no DB required)
# ---------------------------------------------------------------------------


class TestFactoryUnit:
    def test_memory_backend_returns_in_memory_repo(self, monkeypatch) -> None:
        # Explicitly set to ``memory`` so the test is independent of any value
        # configured in the local ``.env`` file (pydantic-settings reads ``.env``
        # even after ``monkeypatch.delenv``).
        monkeypatch.setenv("TODO_REPOSITORY_BACKEND", "memory")
        from concierge.settings import get_todo_settings
        from concierge.todo.infrastructure.persistence.factory import (
            _get_cached_engine,
        )
        from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository

        get_todo_settings.cache_clear()
        _get_cached_engine.cache_clear()

        from concierge.todo.infrastructure.persistence import factory

        repo = factory.get_task_repository()
        assert isinstance(repo, InMemoryTaskRepository)

    def test_unknown_backend_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("TODO_REPOSITORY_BACKEND", "unknown-backend")
        from concierge.settings import get_todo_settings
        from concierge.todo.infrastructure.persistence import factory
        from concierge.todo.infrastructure.persistence.factory import _get_cached_engine

        get_todo_settings.cache_clear()
        _get_cached_engine.cache_clear()

        # ``pydantic.ValidationError`` (a ``ValueError`` subclass) is raised
        # when ``TODO_REPOSITORY_BACKEND`` cannot be parsed into a
        # ``TodoRepositoryBackend`` enum value.
        with pytest.raises(ValueError, match="repository_backend"):
            factory.get_task_repository()

    def test_azure_entra_credential_path(self, monkeypatch) -> None:
        """Azure Entra token should be used as password when use_entra_auth=True."""
        monkeypatch.setenv("AZURE_USE_ENTRA_AUTH", "true")
        monkeypatch.setenv("AZURE_DBUSER", "myuser")
        monkeypatch.setenv("AZURE_DBHOST", "myhost.postgres.database.azure.com")
        monkeypatch.setenv("AZURE_DBNAME", "mydb")

        fake_token = MagicMock()
        fake_token.token = "fake-entra-token"

        with patch("azure.identity.DefaultAzureCredential") as MockCred:
            MockCred.return_value.get_token.return_value = fake_token
            from concierge.settings import get_azure_postgres_settings

            # Clear cached settings so env-vars take effect.
            get_azure_postgres_settings.cache_clear()
            from concierge.todo.infrastructure.persistence.factory import _resolve_azure_credentials

            user, password = _resolve_azure_credentials()

        assert user == "myuser"
        assert password == "fake-entra-token"

    def test_azure_password_fallback(self, monkeypatch) -> None:
        """When use_entra_auth=False, AZURE_DBPASSWORD must be used."""
        monkeypatch.setenv("AZURE_USE_ENTRA_AUTH", "false")
        monkeypatch.setenv("AZURE_DBUSER", "dbuser")
        monkeypatch.setenv("AZURE_DBPASSWORD", "secretpw")
        monkeypatch.setenv("AZURE_DBHOST", "myhost.postgres.database.azure.com")
        monkeypatch.setenv("AZURE_DBNAME", "mydb")

        from concierge.settings import get_azure_postgres_settings

        get_azure_postgres_settings.cache_clear()
        from concierge.todo.infrastructure.persistence.factory import _resolve_azure_credentials

        user, password = _resolve_azure_credentials()
        assert user == "dbuser"
        assert password == "secretpw"


# ---------------------------------------------------------------------------
# Integration tests (real PostgreSQL via testcontainers)
# ---------------------------------------------------------------------------


def _pg_container_repo():
    """Start a PostgreSQL container and return a configured repository."""
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("pgvector/pgvector:pg18")
    container.start()
    url = container.get_connection_url().replace("psycopg2", "psycopg")
    from sqlalchemy import create_engine

    engine = create_engine(url, pool_pre_ping=True)
    repo = SqlAlchemyTaskRepository(engine, table_name="todo_tasks")
    repo.init_schema()
    return repo, container


@pytest.fixture(scope="module")
def pg_repo():
    repo, container = _pg_container_repo()
    yield repo
    container.stop()


@pytest.mark.integration
class TestSqlAlchemyTaskRepositoryIntegration:
    """Full CRUD tests against a real PostgreSQL container."""

    def test_save_and_find_by_id(self, pg_repo) -> None:
        task = Task(title="pg task")
        pg_repo.save(task)
        found = pg_repo.find_by_id(task.id)
        assert found is not None
        assert found.title == "pg task"

    def test_find_by_id_returns_none_for_missing(self, pg_repo) -> None:
        assert pg_repo.find_by_id(uuid.uuid4()) is None

    def test_find_all_with_status_filter(self, pg_repo) -> None:
        pg_repo.save(Task(title="filter-todo"))
        pg_repo.save(Task(title="filter-done", status=TaskStatus.DONE))
        done = pg_repo.find_all(status=TaskStatus.DONE)
        assert any(t.title == "filter-done" for t in done)
        todo = pg_repo.find_all(status=TaskStatus.TODO)
        assert any(t.title == "filter-todo" for t in todo)

    def test_update_task(self, pg_repo) -> None:
        task = Task(title="update-me")
        pg_repo.save(task)
        task.update(title="updated-pg")
        pg_repo.save(task)
        found = pg_repo.find_by_id(task.id)
        assert found is not None
        assert found.title == "updated-pg"

    def test_delete_task(self, pg_repo) -> None:
        task = Task(title="delete-me-pg")
        pg_repo.save(task)
        assert pg_repo.delete(task.id) is True
        assert pg_repo.find_by_id(task.id) is None

    def test_delete_missing_returns_false(self, pg_repo) -> None:
        assert pg_repo.delete(uuid.uuid4()) is False

    def test_ping(self, pg_repo) -> None:
        pg_repo.ping()  # Should not raise.
