from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Final
from uuid import UUID, uuid4

from concierge.todo.domain.exceptions import TaskValidationError
from concierge.todo.domain.value_objects import TaskStatus

MAX_TITLE_LENGTH: Final[int] = 200
MAX_DESCRIPTION_LENGTH: Final[int] = 2000


class _Unset:
    pass


UNSET = _Unset()


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Task:
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _validate_title(self.title))
        object.__setattr__(self, "description", _validate_description(self.description))
        object.__setattr__(self, "created_at", _ensure_utc(self.created_at))
        object.__setattr__(self, "updated_at", _ensure_utc(self.updated_at))

    @classmethod
    def create(
        cls,
        title: str,
        description: str | None = None,
        *,
        task_id: UUID | None = None,
        now: datetime | None = None,
    ) -> Task:
        timestamp = _ensure_utc(now or utc_now())
        return cls(
            id=task_id or uuid4(),
            title=title,
            description=description,
            status=TaskStatus.TODO,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def update(
        self,
        *,
        title: str | _Unset = UNSET,
        description: str | None | _Unset = UNSET,
        status: TaskStatus | _Unset = UNSET,
        now: datetime | None = None,
    ) -> Task:
        next_title = self.title if isinstance(title, _Unset) else title
        next_description = self.description if isinstance(description, _Unset) else description
        next_status = self.status if isinstance(status, _Unset) else status
        return replace(
            self,
            title=_validate_title(next_title),
            description=_validate_description(next_description),
            status=next_status,
            updated_at=_ensure_utc(now or utc_now()),
        )

    def complete(self, *, now: datetime | None = None) -> Task:
        return self.update(status=TaskStatus.DONE, now=now)


def _validate_title(title: str) -> str:
    normalized = title.strip()
    if not normalized:
        raise TaskValidationError("Task title must be between 1 and 200 characters.")
    if len(normalized) > MAX_TITLE_LENGTH:
        raise TaskValidationError("Task title must be at most 200 characters.")
    return normalized


def _validate_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = description.strip()
    if not normalized:
        return None
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise TaskValidationError("Task description must be at most 2000 characters.")
    return normalized


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
