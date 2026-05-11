from __future__ import annotations

from collections.abc import Sequence

from concierge.todo.application.dtos.task_dtos import TaskResponse
from concierge.todo.domain.exceptions import DomainError
from concierge.todo.interfaces.presenters.base import BaseTaskPresenter, Presentation


class CliTaskPresenter(BaseTaskPresenter):
    def present_task(self, task: TaskResponse, *, status_code: int = 200) -> Presentation:
        return Presentation(
            body=(
                f"id: {task.id}\n"
                f"title: {task.title}\n"
                f"description: {task.description or '-'}\n"
                f"status: {task.status.value}\n"
                f"created_at: {task.created_at.isoformat()}\n"
                f"updated_at: {task.updated_at.isoformat()}"
            ),
            status_code=status_code,
        )

    def present_tasks(self, tasks: Sequence[TaskResponse]) -> Presentation:
        if not tasks:
            return Presentation(body="No tasks found.")
        return Presentation(body="\n\n".join(self.present_task(task).body for task in tasks))

    def present_deleted(self, task_id):
        return Presentation(body=f"Deleted task {task_id}.")

    def present_error(self, error: DomainError) -> Presentation:
        presentation = super().present_error(error)
        detail = presentation.body["detail"]
        return Presentation(body=detail, status_code=presentation.status_code, exit_code=presentation.exit_code)
