from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from concierge.cloud_agent.domain.value_objects import TaskStatus


class DispatchTaskRequest(BaseModel):
    agent_type: str = Field(..., min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    max_retries: int | None = Field(None, ge=0)


class UpdateTaskRequest(BaseModel):
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    agent_type: str
    payload: dict[str, Any]
    status: TaskStatus
    result: dict[str, Any] | None
    error: str | None
    retry_count: int
    max_retries: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    agent_types: list[str]
