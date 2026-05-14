from concierge.todo.domain.entities import Task
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository


def test_memory_repository_crud() -> None:
    repo = InMemoryTaskRepository()
    task = Task(title="task 1")

    repo.save(task)
    assert repo.find_by_id(task.id) is not None
    assert len(repo.find_all()) == 1
    assert repo.delete(task.id) is True
    assert repo.find_by_id(task.id) is None


def test_memory_repository_status_filter() -> None:
    repo = InMemoryTaskRepository()
    repo.save(Task(title="todo"))
    repo.save(Task(title="done", status=TaskStatus.DONE))

    tasks = repo.find_all(status=TaskStatus.DONE)
    assert len(tasks) == 1
    assert tasks[0].status == TaskStatus.DONE
