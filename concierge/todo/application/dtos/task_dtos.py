from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from concierge.todo.domain.entities.task import UNSET, Task, _Unset
from concierge.todo.domain.value_objects import TaskStatus


@dataclass(frozen=True, slots=True)
class CreateTaskRequest:
    title: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ListTasksRequest:
    status: TaskStatus | None = None


@dataclass(frozen=True, slots=True)
class UpdateTaskRequest:
    title: str | _Unset = UNSET
    description: str | None | _Unset = UNSET
    status: TaskStatus | _Unset = UNSET


@dataclass(frozen=True, slots=True)
class TaskResponse:
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, task: Task) -> TaskResponse:
        return cls(
            id=task.id,
            title=task.title,
            description=task.description,
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
