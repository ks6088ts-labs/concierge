import uuid

import pytest

from concierge.todo.application.use_cases import (
    CompleteTaskUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from concierge.todo.domain.exceptions import TaskNotFoundError
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository


def test_create_get_and_list_use_cases() -> None:
    repo = InMemoryTaskRepository()
    created = CreateTaskUseCase(repo).execute(title="buy milk")

    fetched = GetTaskUseCase(repo).execute(created.id)
    listed = ListTasksUseCase(repo).execute()

    assert fetched.id == created.id
    assert len(listed) == 1


def test_update_complete_delete_use_cases() -> None:
    repo = InMemoryTaskRepository()
    created = CreateTaskUseCase(repo).execute(title="t1")

    updated = UpdateTaskUseCase(repo).execute(created.id, title="t2", description="d", status=TaskStatus.IN_PROGRESS)
    completed = CompleteTaskUseCase(repo).execute(created.id)
    DeleteTaskUseCase(repo).execute(created.id)

    assert updated.title == "t2"
    assert updated.status == TaskStatus.IN_PROGRESS
    assert completed.status == TaskStatus.DONE
    assert repo.find_by_id(created.id) is None


@pytest.mark.parametrize(
    "operation",
    [
        lambda repo, tid: GetTaskUseCase(repo).execute(tid),
        lambda repo, tid: UpdateTaskUseCase(repo).execute(tid, title="x"),
        lambda repo, tid: CompleteTaskUseCase(repo).execute(tid),
        lambda repo, tid: DeleteTaskUseCase(repo).execute(tid),
    ],
)
def test_missing_task_raises_not_found(operation) -> None:
    repo = InMemoryTaskRepository()

    with pytest.raises(TaskNotFoundError):
        operation(repo, uuid.uuid4())
