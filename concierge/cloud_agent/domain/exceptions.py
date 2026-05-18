from __future__ import annotations

import uuid


class TaskNotFoundError(Exception):
    """Raised when a task is not found."""

    def __init__(self, task_id: uuid.UUID):
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class TaskValidationError(Exception):
    """Raised when task data fails validation."""

    def __init__(self, message: str):
        super().__init__(message)


class TaskStateError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, message: str):
        super().__init__(message)


class QueueError(Exception):
    """Raised when a queue operation fails."""

    def __init__(self, message: str):
        super().__init__(message)
