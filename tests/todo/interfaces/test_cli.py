from __future__ import annotations

import re

from typer.testing import CliRunner

from concierge.todo.infrastructure.cli.typer_app import app

runner = CliRunner()


def test_cli_supports_crud_flow():
    create = runner.invoke(app, ["task", "create", "--title", "Buy milk", "--description", "2 bottles"])
    assert create.exit_code == 0
    match = re.search(r"id: ([0-9a-f-]+)", create.stdout)
    assert match is not None
    task_id = match.group(1)

    listed = runner.invoke(app, ["task", "list", "--status", "TODO"])
    assert listed.exit_code == 0
    assert task_id in listed.stdout

    fetched = runner.invoke(app, ["task", "get", task_id])
    assert fetched.exit_code == 0
    assert "title: Buy milk" in fetched.stdout

    updated = runner.invoke(app, ["task", "update", task_id, "--status", "IN_PROGRESS"])
    assert updated.exit_code == 0
    assert "status: IN_PROGRESS" in updated.stdout

    completed = runner.invoke(app, ["task", "complete", task_id])
    assert completed.exit_code == 0
    assert "status: DONE" in completed.stdout

    deleted = runner.invoke(app, ["task", "delete", task_id])
    assert deleted.exit_code == 0
    assert f"Deleted task {task_id}." in deleted.stdout
