from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from concierge.todo.domain.value_objects import TaskStatus


class TaskCreateSchema(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(str_strip_whitespace=True)


class TaskUpdateSchema(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class TaskResponseSchema(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


class TaskListResponseSchema(BaseModel):
    tasks: list[TaskResponseSchema]


class ErrorResponseSchema(BaseModel):
    error: str
    detail: str


class HealthResponseSchema(BaseModel):
    status: str
