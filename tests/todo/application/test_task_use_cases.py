from uuid import UUID, uuid4

from concierge.todo.application.dtos.task_dtos import CreateTaskRequest, ListTasksRequest, UpdateTaskRequest
from concierge.todo.application.use_cases.task_use_cases import (
    CompleteTaskUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from concierge.todo.domain.entities.task import Task
from concierge.todo.domain.value_objects import TaskStatus


class FakeTaskRepository:
    def __init__(self):
        self.tasks: dict[UUID, Task] = {}

    def create(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def get(self, task_id: UUID) -> Task | None:
        return self.tasks.get(task_id)

    def list(self, status: TaskStatus | None = None) -> list[Task]:
        tasks = list(self.tasks.values())
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return tasks

    def update(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def delete(self, task_id: UUID) -> bool:
        return self.tasks.pop(task_id, None) is not None


def test_use_cases_support_crud_flow():
    repository = FakeTaskRepository()
    create = CreateTaskUseCase(repository)
    get = GetTaskUseCase(repository)
    list_tasks = ListTasksUseCase(repository)
    update = UpdateTaskUseCase(repository)
    complete = CompleteTaskUseCase(repository)
    delete = DeleteTaskUseCase(repository)

    created = create.execute(CreateTaskRequest(title="Buy milk", description="2 bottles"))
    assert created.is_ok
    assert created.value is not None
    task_id = created.value.id

    fetched = get.execute(task_id)
    assert fetched.value is not None
    assert fetched.value.title == "Buy milk"

    updated = update.execute(task_id, UpdateTaskRequest(status=TaskStatus.IN_PROGRESS))
    assert updated.value is not None
    assert updated.value.status == TaskStatus.IN_PROGRESS

    completed = complete.execute(task_id)
    assert completed.value is not None
    assert completed.value.status == TaskStatus.DONE

    listed = list_tasks.execute(ListTasksRequest(status=TaskStatus.DONE))
    assert listed.value is not None
    assert [task.id for task in listed.value] == [task_id]

    deleted = delete.execute(task_id)
    assert deleted.is_ok
    assert repository.get(task_id) is None


def test_delete_returns_error_for_missing_task():
    result = DeleteTaskUseCase(FakeTaskRepository()).execute(uuid4())

    assert result.is_error
