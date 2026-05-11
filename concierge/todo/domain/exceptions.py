from uuid import UUID


class DomainError(Exception):
    """Base exception for Todo domain errors."""


class TaskValidationError(DomainError):
    """Raised when task data violates domain invariants."""


class TaskNotFoundError(DomainError):
    """Raised when a task cannot be found."""

    def __init__(self, task_id: UUID):
        self.task_id = task_id
        super().__init__(f"Task {task_id} was not found.")
