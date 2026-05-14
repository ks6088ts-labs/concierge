from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from concierge.todo.domain.exceptions import TaskValidationError
from concierge.todo.domain.value_objects import TaskStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Task:
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self._validate_title(self.title)
        self._validate_description(self.description)

    @staticmethod
    def _validate_title(title: str) -> None:
        if not 1 <= len(title) <= 200:
            raise TaskValidationError("title must be between 1 and 200 characters")

    @staticmethod
    def _validate_description(description: str | None) -> None:
        if description is not None and len(description) > 2000:
            raise TaskValidationError("description must be 2000 characters or fewer")
