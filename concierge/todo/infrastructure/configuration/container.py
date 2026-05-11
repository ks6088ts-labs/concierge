from functools import lru_cache

from concierge.todo.application.use_cases.task_use_cases import (
    CompleteTaskUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository
from concierge.todo.interfaces.controllers.task_controller import TaskController


@lru_cache(maxsize=1)
def get_task_repository() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


def reset_task_repository() -> None:
    get_task_repository().clear()


def build_task_controller() -> TaskController:
    repository = get_task_repository()
    return TaskController(
        create_task=CreateTaskUseCase(repository),
        get_task=GetTaskUseCase(repository),
        list_tasks=ListTasksUseCase(repository),
        update_task=UpdateTaskUseCase(repository),
        complete_task=CompleteTaskUseCase(repository),
        delete_task=DeleteTaskUseCase(repository),
    )
