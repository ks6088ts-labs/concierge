import pytest

from concierge.todo.infrastructure.configuration.container import reset_task_repository


@pytest.fixture(autouse=True)
def reset_todo_state():
    reset_task_repository()
    yield
    reset_task_repository()
