from __future__ import annotations

from dataclasses import dataclass

from concierge.todo.application.dtos.task_dtos import TaskResponse


@dataclass(frozen=True, slots=True)
class TaskViewModel:
    id: str
    title: str
    description: str | None
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_response(cls, task: TaskResponse) -> TaskViewModel:
        return cls(
            id=str(task.id),
            title=task.title,
            description=task.description,
            status=task.status.value,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
        )


@dataclass(frozen=True, slots=True)
class TaskListViewModel:
    tasks: list[TaskViewModel]

    @classmethod
    def from_responses(cls, tasks: list[TaskResponse]) -> TaskListViewModel:
        return cls(tasks=[TaskViewModel.from_response(task) for task in tasks])
