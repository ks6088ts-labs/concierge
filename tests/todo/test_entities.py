from datetime import timezone

import pytest

from concierge.todo.domain.entities import Task
from concierge.todo.domain.exceptions import TaskValidationError
from concierge.todo.domain.value_objects import TaskStatus


def test_task_defaults() -> None:
    task = Task(title="buy milk")

    assert task.status == TaskStatus.TODO
    assert task.description is None
    assert task.created_at.tzinfo == timezone.utc
    assert task.updated_at.tzinfo == timezone.utc


def test_task_validates_title() -> None:
    with pytest.raises(TaskValidationError):
        Task(title="")


def test_task_validates_description() -> None:
    with pytest.raises(TaskValidationError):
        Task(title="ok", description="x" * 2001)
