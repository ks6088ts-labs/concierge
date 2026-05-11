from concierge.todo.domain.entities.task import Task
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository


def test_memory_repository_lists_tasks_in_creation_order_and_filters_by_status():
    repository = InMemoryTaskRepository()
    todo_task = repository.create(Task.create(title="First"))
    done_task = repository.create(Task.create(title="Second").complete())

    assert [task.id for task in repository.list()] == [todo_task.id, done_task.id]
    assert [task.id for task in repository.list(status=TaskStatus.DONE)] == [done_task.id]


def test_memory_repository_delete_returns_false_when_task_missing():
    repository = InMemoryTaskRepository()

    assert repository.delete(Task.create(title="missing").id) is False
