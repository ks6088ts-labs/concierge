"""Tests for SqlAlchemyTaskRepository (cloud_agent)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text

from concierge.agents.domain.agent_types import AgentType
from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.value_objects import TaskStatus
from concierge.cloud_agent.infrastructure.persistence.postgres import SqlAlchemyTaskRepository


def _make_sqlite_repo() -> SqlAlchemyTaskRepository:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    repo = SqlAlchemyTaskRepository(engine, table_name="cloud_agent_tasks")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cloud_agent_tasks (
                    id            TEXT PRIMARY KEY,
                    agent_type    VARCHAR(100)  NOT NULL,
                    payload       TEXT          NOT NULL,
                    status        VARCHAR(32)   NOT NULL,
                    result        TEXT,
                    error         TEXT,
                    retry_count   INTEGER       NOT NULL DEFAULT 0,
                    max_retries   INTEGER       NOT NULL DEFAULT 3,
                    created_at    DATETIME      NOT NULL,
                    updated_at    DATETIME      NOT NULL,
                    started_at    DATETIME,
                    finished_at   DATETIME
                )
                """
            )
        )
    return repo


class TestSqlAlchemyTaskRepositoryUnit:
    def test_save_and_find_by_id(self) -> None:
        repo = _make_sqlite_repo()
        task = Task(agent_type=AgentType.ECHO, payload={"k": "v"})
        repo.save(task)
        found = repo.find_by_id(task.id)
        assert found is not None
        assert found.id == task.id
        assert found.agent_type == AgentType.ECHO
        assert found.payload == {"k": "v"}

    def test_find_by_id_returns_none_for_missing(self) -> None:
        repo = _make_sqlite_repo()
        assert repo.find_by_id(uuid.uuid4()) is None

    def test_find_all_empty(self) -> None:
        repo = _make_sqlite_repo()
        assert repo.find_all() == []

    def test_find_all_with_status_filter(self) -> None:
        repo = _make_sqlite_repo()
        t1 = Task(agent_type=AgentType.ECHO, payload={})
        t2 = Task(agent_type=AgentType.ECHO, payload={})
        t2.mark_running()
        t2.mark_succeeded({"r": 1})
        repo.save(t1)
        repo.save(t2)
        queued = repo.find_all(status=TaskStatus.QUEUED)
        assert len(queued) == 1
        assert queued[0].id == t1.id

    def test_find_all_with_agent_type_filter(self) -> None:
        repo = _make_sqlite_repo()
        repo.save(Task(agent_type=AgentType.ECHO, payload={}))
        repo.save(Task(agent_type="other", payload={}))
        echo = repo.find_all(agent_type=AgentType.ECHO)
        assert len(echo) == 1

    def test_save_updates_existing(self) -> None:
        repo = _make_sqlite_repo()
        task = Task(agent_type=AgentType.ECHO, payload={})
        repo.save(task)
        task.mark_running()
        repo.save(task)
        found = repo.find_by_id(task.id)
        assert found is not None
        assert found.status == TaskStatus.RUNNING

    def test_delete_existing(self) -> None:
        repo = _make_sqlite_repo()
        task = Task(agent_type=AgentType.ECHO, payload={})
        repo.save(task)
        assert repo.delete(task.id) is True
        assert repo.find_by_id(task.id) is None

    def test_delete_missing_returns_false(self) -> None:
        repo = _make_sqlite_repo()
        assert repo.delete(uuid.uuid4()) is False

    def test_count(self) -> None:
        repo = _make_sqlite_repo()
        repo.save(Task(agent_type=AgentType.ECHO, payload={}))
        repo.save(Task(agent_type=AgentType.ECHO, payload={}))
        assert repo.count() == 2
        assert repo.count(agent_type=AgentType.ECHO) == 2
        assert repo.count(agent_type="other") == 0

    def test_limit_offset(self) -> None:
        repo = _make_sqlite_repo()
        for _ in range(5):
            repo.save(Task(agent_type=AgentType.ECHO, payload={}))
        page1 = repo.find_all(limit=3, offset=0)
        page2 = repo.find_all(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2


# ---------------------------------------------------------------------------
# Integration tests (real PostgreSQL via testcontainers)
# ---------------------------------------------------------------------------


def _pg_container_repo():
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("pgvector/pgvector:pg18")
    container.start()
    url = container.get_connection_url().replace("psycopg2", "psycopg")
    engine = create_engine(url, pool_pre_ping=True)
    repo = SqlAlchemyTaskRepository(engine, table_name="cloud_agent_tasks")
    repo.init_schema()
    return repo, container


@pytest.fixture(scope="module")
def pg_repo():
    from tests.conftest import skip_if_docker_unavailable

    skip_if_docker_unavailable()
    repo, container = _pg_container_repo()
    yield repo
    container.stop()


@pytest.mark.integration
class TestSqlAlchemyTaskRepositoryIntegration:
    def test_save_and_find_by_id(self, pg_repo) -> None:
        task = Task(agent_type=AgentType.ECHO, payload={"pg": True})
        pg_repo.save(task)
        found = pg_repo.find_by_id(task.id)
        assert found is not None
        assert found.payload == {"pg": True}

    def test_find_all_with_status_filter(self, pg_repo) -> None:
        t = Task(agent_type=AgentType.ECHO, payload={})
        t.mark_running()
        t.mark_succeeded({"ok": 1})
        pg_repo.save(t)
        succeeded = pg_repo.find_all(status=TaskStatus.SUCCEEDED)
        assert any(x.id == t.id for x in succeeded)

    def test_delete_task(self, pg_repo) -> None:
        task = Task(agent_type=AgentType.ECHO, payload={})
        pg_repo.save(task)
        assert pg_repo.delete(task.id) is True
        assert pg_repo.find_by_id(task.id) is None

    def test_ping(self, pg_repo) -> None:
        pg_repo.ping()
