import enum


class TaskStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"

    def can_transition_to(self, new_status: "TaskStatus") -> bool:
        """Return True if this status can transition to *new_status*."""
        allowed: dict[TaskStatus, set[TaskStatus]] = {
            TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
            TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED},
            TaskStatus.FAILED: {TaskStatus.QUEUED, TaskStatus.DEAD_LETTER},
            TaskStatus.SUCCEEDED: set(),
            TaskStatus.CANCELLED: set(),
            TaskStatus.DEAD_LETTER: set(),
        }
        return new_status in allowed.get(self, set())
