from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from concierge.todo.domain.exceptions import TaskNotFoundError, TaskValidationError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TaskNotFoundError)
    async def task_not_found_handler(_: Request, exc: TaskNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TaskValidationError)
    async def task_validation_handler(_: Request, exc: TaskValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
