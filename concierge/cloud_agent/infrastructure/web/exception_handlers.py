from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from concierge.cloud_agent.domain.exceptions import (
    AgentNotFoundError,
    QueueError,
    TaskNotFoundError,
    TaskStateError,
    TaskValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TaskNotFoundError)
    async def task_not_found_handler(_: Request, exc: TaskNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TaskValidationError)
    async def task_validation_handler(_: Request, exc: TaskValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(TaskStateError)
    async def task_state_handler(_: Request, exc: TaskStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(AgentNotFoundError)
    async def agent_not_found_handler(_: Request, exc: AgentNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(QueueError)
    async def queue_error_handler(_: Request, exc: QueueError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
