from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

import typer
from dotenv import load_dotenv

from concierge.loggers import get_logger
from concierge.observability import disable_tracing, enable_mlflow, enable_tracing
from concierge.settings import TodoRepositoryBackend, get_todo_settings
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
from concierge.todo.infrastructure.persistence.factory import get_task_repository

app = typer.Typer(add_completion=False, help="Todo CLI")
task_app = typer.Typer(help="Task commands")
db_app = typer.Typer(help="Database management commands")
app.add_typer(task_app, name="task")
app.add_typer(db_app, name="db")
logger = get_logger("concierge.todo")
repository = get_task_repository()


@app.callback()
def _bootstrap(
    tracing: Annotated[
        bool,
        typer.Option(
            "--tracing",
            "-t",
            help=(
                "Enable Microsoft Foundry / Azure Monitor tracing for LangChain runs. "
                "See https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-traces"
            ),
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose (DEBUG) logging",
        ),
    ] = False,
    mlflow: Annotated[
        bool,
        typer.Option(
            "--mlflow",
            "-m",
            help=(
                "Enable MLflow autologging for LangChain / LangGraph runs. "
                "See https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/"
            ),
        ),
    ] = False,
) -> None:
    load_dotenv()
    if tracing:
        enable_tracing()
    else:
        disable_tracing()
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    if mlflow:
        enable_mlflow()


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


def _require_sql_backend() -> None:
    """Exit with an error message when the backend is ``memory``."""
    backend = get_todo_settings().repository_backend
    if backend is TodoRepositoryBackend.MEMORY:
        typer.echo(
            "The 'db' commands are not applicable for the 'memory' backend. "
            f"Set TODO_REPOSITORY_BACKEND to "
            f"'{TodoRepositoryBackend.POSTGRES.value}' or "
            f"'{TodoRepositoryBackend.AZURE_POSTGRES.value}'.",
            err=True,
        )
        raise typer.Exit(code=1)


@db_app.command("init")
def db_init() -> None:
    """Create the todo_tasks table (CREATE TABLE IF NOT EXISTS) in the current backend."""
    _require_sql_backend()
    from concierge.todo.infrastructure.persistence.postgres import SqlAlchemyTaskRepository

    repo = repository
    if not isinstance(repo, SqlAlchemyTaskRepository):
        typer.echo("Backend does not support schema initialisation.", err=True)
        raise typer.Exit(code=1)
    repo.init_schema()
    typer.echo("Database schema initialised successfully.")


@db_app.command("drop")
def db_drop(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Drop the todo_tasks table from the current backend."""
    _require_sql_backend()
    from concierge.todo.infrastructure.persistence.postgres import SqlAlchemyTaskRepository

    repo = repository
    if not isinstance(repo, SqlAlchemyTaskRepository):
        typer.echo("Backend does not support schema management.", err=True)
        raise typer.Exit(code=1)
    if not yes:
        typer.confirm("This will drop the todo_tasks table. Continue?", abort=True)
    repo.drop_schema()
    typer.echo("Table dropped.")


@db_app.command("ping")
def db_ping() -> None:
    """Check connectivity to the current backend (SELECT 1)."""
    _require_sql_backend()
    from concierge.todo.infrastructure.persistence.postgres import SqlAlchemyTaskRepository

    repo = repository
    if not isinstance(repo, SqlAlchemyTaskRepository):
        typer.echo("Backend does not support ping.", err=True)
        raise typer.Exit(code=1)
    repo.ping()
    typer.echo("Connection OK.")


if __name__ == "__main__":
    app()
