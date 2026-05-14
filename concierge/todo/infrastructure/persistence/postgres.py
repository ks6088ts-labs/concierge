"""SQLAlchemy Core-based PostgreSQL implementation of TaskRepository.

Uses SQLAlchemy Core (not ORM) with explicit queries and short-lived transactions
via ``engine.begin()``. The ``Task`` domain object is mapped to/from plain row
dicts without any ORM instrumentation, keeping the domain layer clean.
"""

from __future__ import annotations

import uuid
from datetime import timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, MetaData, String, Table, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import DateTime

from concierge.todo.domain.entities import Task
from concierge.todo.domain.value_objects import TaskStatus

if TYPE_CHECKING:
    from sqlalchemy import Engine

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_metadata = MetaData()

_DEFAULT_TABLE_NAME = "todo_tasks"


def _make_table(table_name: str) -> Table:
    """Return the SQLAlchemy Table definition for *table_name*."""
    return Table(
        table_name,
        _metadata,
        Column("id", PG_UUID(as_uuid=True), primary_key=True),
        Column("title", String(200), nullable=False),
        Column("description", String(2000), nullable=True),
        Column("status", String(32), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        extend_existing=True,
    )


# ---------------------------------------------------------------------------
# Row ↔ Domain helpers
# ---------------------------------------------------------------------------


def _task_to_row(task: Task) -> dict:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _row_to_task(row) -> Task:
    # SQLAlchemy Row objects support attribute access.
    created_at = row.created_at
    updated_at = row.updated_at
    # SQLite stores datetimes as strings; parse them back to datetime objects.
    if isinstance(created_at, str):
        from datetime import datetime

        created_at = datetime.fromisoformat(created_at)
    if isinstance(updated_at, str):
        from datetime import datetime

        updated_at = datetime.fromisoformat(updated_at)
    # Ensure timezone-aware datetimes (PostgreSQL TIMESTAMPTZ returns aware).
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return Task(
        id=row.id if isinstance(row.id, uuid.UUID) else uuid.UUID(str(row.id)),
        title=row.title,
        description=row.description,
        status=TaskStatus(row.status),
        created_at=created_at,
        updated_at=updated_at,
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class SqlAlchemyTaskRepository:
    """``TaskRepository`` backed by PostgreSQL via SQLAlchemy Core.

    Args:
        engine: A SQLAlchemy ``Engine`` connected to the target database.
        table_name: Override the default table name (``todo_tasks``).
    """

    def __init__(self, engine: Engine, table_name: str = _DEFAULT_TABLE_NAME) -> None:
        self._engine = engine
        self._table = _make_table(table_name)

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """Run ``CREATE TABLE IF NOT EXISTS`` and the status index."""
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table.name} (
                        id          UUID PRIMARY KEY,
                        title       VARCHAR(200)  NOT NULL,
                        description VARCHAR(2000),
                        status      VARCHAR(32)   NOT NULL,
                        created_at  TIMESTAMPTZ   NOT NULL,
                        updated_at  TIMESTAMPTZ   NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS idx_{self._table.name}_status ON {self._table.name} (status)")
            )

    def drop_schema(self) -> None:
        """Drop the task table if it exists."""
        with self._engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {self._table.name}"))

    def ping(self) -> None:
        """Execute ``SELECT 1`` to verify the database connection."""
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    # ------------------------------------------------------------------
    # TaskRepository Protocol
    # ------------------------------------------------------------------

    def save(self, task: Task) -> Task:
        """Insert or update *task* (upsert by primary key)."""
        row = _task_to_row(task)
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {self._table.name}
                        (id, title, description, status, created_at, updated_at)
                    VALUES
                        (:id, :title, :description, :status, :created_at, :updated_at)
                    ON CONFLICT (id) DO UPDATE SET
                        title       = EXCLUDED.title,
                        description = EXCLUDED.description,
                        status      = EXCLUDED.status,
                        updated_at  = EXCLUDED.updated_at
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

    def find_all(self, status: TaskStatus | None = None) -> list[Task]:
        with self._engine.connect() as conn:
            if status is None:
                result = conn.execute(text(f"SELECT * FROM {self._table.name}"))
            else:
                result = conn.execute(
                    text(f"SELECT * FROM {self._table.name} WHERE status = :status"),
                    {"status": status.value},
                )
            rows = result.fetchall()
        return [_row_to_task(row) for row in rows]

    def delete(self, task_id: uuid.UUID) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM {self._table.name} WHERE id = :id"),
                {"id": str(task_id)},
            )
        return result.rowcount > 0
