from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from concierge.chat.domain.exceptions import (
    ConversationNotFoundError,
    MessageValidationError,
    ParticipantValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found_handler(_: Request, exc: ConversationNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MessageValidationError)
    async def message_validation_handler(_: Request, exc: MessageValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ParticipantValidationError)
    async def participant_validation_handler(_: Request, exc: ParticipantValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
