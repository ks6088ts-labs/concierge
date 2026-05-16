"""SQLAlchemy Core-based PostgreSQL implementation of TaskRepository for cloud_agent.

Uses SQLAlchemy Core (not ORM) with explicit queries and short-lived transactions.
"""

from __future__ import annotations

import json
import uuid
from datetime import timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, MetaData, String, Table, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import DateTime, Integer, Text

from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.value_objects import TaskStatus

if TYPE_CHECKING:
    from sqlalchemy import Engine

_metadata = MetaData()
_DEFAULT_TABLE_NAME = "cloud_agent_tasks"


def _make_table(table_name: str) -> Table:
    return Table(
        table_name,
        _metadata,
        Column("id", PG_UUID(as_uuid=True), primary_key=True),
        Column("agent_type", String(100), nullable=False),
        Column("payload", Text, nullable=False),
        Column("status", String(32), nullable=False),
        Column("result", Text, nullable=True),
        Column("error", Text, nullable=True),
        Column("retry_count", Integer, nullable=False, default=0),
        Column("max_retries", Integer, nullable=False, default=3),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("started_at", DateTime(timezone=True), nullable=True),
        Column("finished_at", DateTime(timezone=True), nullable=True),
        extend_existing=True,
    )


def _task_to_row(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "agent_type": task.agent_type,
        "payload": json.dumps(task.payload),
        "status": task.status.value,
        "result": json.dumps(task.result) if task.result is not None else None,
        "error": task.error,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
    }


def _parse_dt(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        from datetime import datetime

        value = datetime.fromisoformat(value)
    if hasattr(value, "tzinfo") and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _row_to_task(row: Any) -> Task:
    return Task(
        id=row.id if isinstance(row.id, uuid.UUID) else uuid.UUID(str(row.id)),
        agent_type=row.agent_type,
        payload=json.loads(row.payload),
        status=TaskStatus(row.status),
        result=json.loads(row.result) if row.result else None,
        error=row.error,
        retry_count=row.retry_count,
        max_retries=row.max_retries,
        created_at=_parse_dt(row.created_at),
        updated_at=_parse_dt(row.updated_at),
        started_at=_parse_dt(row.started_at),
        finished_at=_parse_dt(row.finished_at),
    )


class SqlAlchemyTaskRepository:
    """TaskRepository backed by PostgreSQL via SQLAlchemy Core."""

    def __init__(self, engine: Engine, table_name: str = _DEFAULT_TABLE_NAME) -> None:
        self._engine = engine
        self._table = _make_table(table_name)

    def init_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table.name} (
                        id            UUID PRIMARY KEY,
                        agent_type    VARCHAR(100)  NOT NULL,
                        payload       TEXT          NOT NULL,
                        status        VARCHAR(32)   NOT NULL,
                        result        TEXT,
                        error         TEXT,
                        retry_count   INTEGER       NOT NULL DEFAULT 0,
                        max_retries   INTEGER       NOT NULL DEFAULT 3,
                        created_at    TIMESTAMPTZ   NOT NULL,
                        updated_at    TIMESTAMPTZ   NOT NULL,
                        started_at    TIMESTAMPTZ,
                        finished_at   TIMESTAMPTZ
                    )
                    """
                )
            )
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS idx_{self._table.name}_status ON {self._table.name} (status)")
            )
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS idx_{self._table.name}_agent_type ON {self._table.name} (agent_type)")
            )

    def drop_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {self._table.name}"))

    def ping(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def save(self, task: Task) -> Task:
        row = _task_to_row(task)
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {self._table.name}
                        (id, agent_type, payload, status, result, error,
                         retry_count, max_retries, created_at, updated_at,
                         started_at, finished_at)
                    VALUES
                        (:id, :agent_type, :payload, :status, :result, :error,
                         :retry_count, :max_retries, :created_at, :updated_at,
                         :started_at, :finished_at)
                    ON CONFLICT (id) DO UPDATE SET
                        agent_type   = EXCLUDED.agent_type,
                        payload      = EXCLUDED.payload,
                        status       = EXCLUDED.status,
                        result       = EXCLUDED.result,
                        error        = EXCLUDED.error,
                        retry_count  = EXCLUDED.retry_count,
                        max_retries  = EXCLUDED.max_retries,
                        updated_at   = EXCLUDED.updated_at,
                        started_at   = EXCLUDED.started_at,
                        finished_at  = EXCLUDED.finished_at
                    """
                ),
                row,
            )
        return task

    def find_by_id(self, task_id: uuid.UUID) -> Task | None:
        with self._engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM {self._table.name} WHERE id = :id"),
                {"id": str(task_id)},
            )
            row = result.fetchone()
        if row is None:
            return None
        return _row_to_task(row)

    def find_all(
        self,
        status: TaskStatus | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        where_clauses = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            where_clauses.append("status = :status")
            params["status"] = status.value
        if agent_type is not None:
            where_clauses.append("agent_type = :agent_type")
            params["agent_type"] = agent_type
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        sql = f"SELECT * FROM {self._table.name}{where_sql} ORDER BY created_at LIMIT :limit OFFSET :offset"
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.fetchall()
        return [_row_to_task(row) for row in rows]

    def delete(self, task_id: uuid.UUID) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM {self._table.name} WHERE id = :id"),
                {"id": str(task_id)},
            )
        return result.rowcount > 0

    def count(
        self,
        status: TaskStatus | None = None,
        agent_type: str | None = None,
    ) -> int:
        where_clauses = []
        params: dict[str, Any] = {}
        if status is not None:
            where_clauses.append("status = :status")
            params["status"] = status.value
        if agent_type is not None:
            where_clauses.append("agent_type = :agent_type")
            params["agent_type"] = agent_type
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        sql = f"SELECT COUNT(*) FROM {self._table.name}{where_sql}"
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params)
            row = result.fetchone()
        return row[0] if row else 0
