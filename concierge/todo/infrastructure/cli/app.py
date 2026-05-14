from __future__ import annotations

import json
import uuid
from typing import Annotated

import typer

from concierge.loggers import get_logger
from concierge.todo.application.use_cases import (
    CompleteTaskUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from concierge.todo.domain.entities import Task
from concierge.todo.domain.exceptions import TaskNotFoundError, TaskValidationError
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository

app = typer.Typer(add_completion=False, help="Todo CLI")
task_app = typer.Typer(help="Task commands")
app.add_typer(task_app, name="task")
logger = get_logger("concierge.todo")
repository = InMemoryTaskRepository()


def _task_to_dict(task: Task) -> dict[str, object]:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _print_task(task: Task) -> None:
    typer.echo(json.dumps(_task_to_dict(task), ensure_ascii=False))


def _handle_error(exc: Exception) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=1) from exc


@task_app.command("create")
def create_task(
    title: Annotated[str, typer.Option("--title", help="Task title")],
    description: Annotated[str | None, typer.Option("--description", help="Task description")] = None,
) -> None:
    try:
        task = CreateTaskUseCase(repository).execute(title=title, description=description)
        _print_task(task)
    except TaskValidationError as exc:
        _handle_error(exc)


@task_app.command("list")
def list_tasks(
    status: Annotated[TaskStatus | None, typer.Option("--status", help="Filter by status")] = None,
) -> None:
    tasks = ListTasksUseCase(repository).execute(status=status)
    typer.echo(json.dumps([_task_to_dict(task) for task in tasks], ensure_ascii=False))


@task_app.command("get")
def get_task(task_id: uuid.UUID) -> None:
    try:
        task = GetTaskUseCase(repository).execute(task_id)
        _print_task(task)
    except TaskNotFoundError as exc:
        _handle_error(exc)


@task_app.command("update")
def update_task(
    task_id: uuid.UUID,
    title: Annotated[str | None, typer.Option("--title", help="Task title")] = None,
    description: Annotated[str | None, typer.Option("--description", help="Task description")] = None,
    status: Annotated[TaskStatus | None, typer.Option("--status", help="Task status")] = None,
) -> None:
    try:
        task = UpdateTaskUseCase(repository).execute(
            task_id=task_id,
            title=title,
            description=description,
            status=status,
        )
        _print_task(task)
    except (TaskNotFoundError, TaskValidationError) as exc:
        _handle_error(exc)


@task_app.command("complete")
def complete_task(task_id: uuid.UUID) -> None:
    try:
        task = CompleteTaskUseCase(repository).execute(task_id)
        _print_task(task)
    except TaskNotFoundError as exc:
        _handle_error(exc)


@task_app.command("delete")
def delete_task(task_id: uuid.UUID) -> None:
    try:
        DeleteTaskUseCase(repository).execute(task_id)
        typer.echo("deleted")
    except TaskNotFoundError as exc:
        _handle_error(exc)


if __name__ == "__main__":
    app()
