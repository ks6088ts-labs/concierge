from datetime import datetime, timedelta, timezone

import pytest

from concierge.todo.domain.entities.task import Task
from concierge.todo.domain.exceptions import TaskValidationError
from concierge.todo.domain.value_objects import TaskStatus


def test_create_task_defaults_to_todo_status():
    task = Task.create(title="  buy milk  ", description="  2 bottles  ")

    assert task.title == "buy milk"
    assert task.description == "2 bottles"
    assert task.status == TaskStatus.TODO
    assert task.created_at == task.updated_at
    assert task.created_at.tzinfo == timezone.utc


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_create_task_rejects_invalid_titles(title: str):
    with pytest.raises(TaskValidationError):
        Task.create(title=title)


def test_update_task_normalizes_optional_fields():
    task = Task.create(title="Write tests", description="Draft")
    updated = task.update(description="   ", status=TaskStatus.IN_PROGRESS)

    assert updated.description is None
    assert updated.status == TaskStatus.IN_PROGRESS


def test_complete_task_updates_timestamp():
    initial = datetime(2026, 1, 1, tzinfo=timezone.utc)
    completed = Task.create(title="Ship feature", now=initial).complete(now=initial + timedelta(minutes=1))

    assert completed.status == TaskStatus.DONE
    assert completed.updated_at > completed.created_at
