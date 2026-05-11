from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from concierge.todo.application.dtos.task_dtos import TaskResponse
from concierge.todo.domain.exceptions import DomainError, TaskNotFoundError, TaskValidationError
from concierge.todo.interfaces.view_models.base import ErrorViewModel, MessageViewModel
from concierge.todo.interfaces.view_models.task_vm import TaskListViewModel, TaskViewModel


@dataclass(frozen=True, slots=True)
class Presentation:
    body: Any
    status_code: int = 200
    exit_code: int = 0


class BaseTaskPresenter:
    def present_task(self, task: TaskResponse, *, status_code: int = 200) -> Presentation:
        return Presentation(body=asdict(TaskViewModel.from_response(task)), status_code=status_code)

    def present_tasks(self, tasks: list[TaskResponse]) -> Presentation:
        return Presentation(body=asdict(TaskListViewModel.from_responses(tasks)))

    def present_deleted(self, task_id: UUID) -> Presentation:
        return Presentation(body=asdict(MessageViewModel(detail=f"Deleted task {task_id}.")), status_code=204)

    def present_error(self, error: DomainError) -> Presentation:
        if isinstance(error, TaskNotFoundError):
            return Presentation(
                body=asdict(ErrorViewModel(error="task_not_found", detail=str(error))),
                status_code=404,
                exit_code=1,
            )
        if isinstance(error, TaskValidationError):
            return Presentation(
                body=asdict(ErrorViewModel(error="task_validation_error", detail=str(error))),
                status_code=400,
                exit_code=2,
            )
        return Presentation(
            body=asdict(ErrorViewModel(error="domain_error", detail=str(error))), status_code=400, exit_code=1
        )
