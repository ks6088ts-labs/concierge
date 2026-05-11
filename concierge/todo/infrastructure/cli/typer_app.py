from __future__ import annotations

from uuid import UUID

import typer

from concierge.todo.application.dtos.task_dtos import CreateTaskRequest, ListTasksRequest, UpdateTaskRequest
from concierge.todo.domain.entities.task import UNSET
from concierge.todo.domain.exceptions import DomainError
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.configuration.container import build_task_controller
from concierge.todo.interfaces.presenters.cli import CliTaskPresenter

app = typer.Typer(add_completion=False, help="Todo CLI")
task_app = typer.Typer(add_completion=False, help="Manage tasks")
app.add_typer(task_app, name="task")


@task_app.command("create")
def create_task(
    title: str = typer.Option(..., "--title"), description: str | None = typer.Option(None, "--description")
) -> None:
    _run(
        lambda: CliTaskPresenter().present_task(
            build_task_controller().create(CreateTaskRequest(title=title, description=description)), status_code=201
        )
    )


@task_app.command("list")
def list_tasks(status: TaskStatus | None = typer.Option(None, "--status")) -> None:
    _run(lambda: CliTaskPresenter().present_tasks(build_task_controller().list(ListTasksRequest(status=status))))


@task_app.command("get")
def get_task(task_id: UUID) -> None:
    _run(lambda: CliTaskPresenter().present_task(build_task_controller().get(task_id)))


@task_app.command("update")
def update_task(
    task_id: UUID,
    title: str | None = typer.Option(None, "--title"),
    description: str | None = typer.Option(None, "--description"),
    status: TaskStatus | None = typer.Option(None, "--status"),
) -> None:
    title_value = UNSET if title is None else title
    description_value = UNSET if description is None else (description or None)
    status_value = UNSET if status is None else status
    _run(
        lambda: CliTaskPresenter().present_task(
            build_task_controller().update(
                task_id,
                UpdateTaskRequest(title=title_value, description=description_value, status=status_value),
            )
        )
    )


@task_app.command("complete")
def complete_task(task_id: UUID) -> None:
    _run(lambda: CliTaskPresenter().present_task(build_task_controller().complete(task_id)))


@task_app.command("delete")
def delete_task(task_id: UUID) -> None:
    _run(
        lambda: (
            build_task_controller().delete(task_id),
            CliTaskPresenter().present_deleted(task_id),
        )[1]
    )


def _run(action) -> None:
    presenter = CliTaskPresenter()
    try:
        presentation = action()
    except DomainError as error:
        failure = presenter.present_error(error)
        typer.echo(failure.body, err=True)
        raise typer.Exit(code=failure.exit_code) from error
    typer.echo(presentation.body)
