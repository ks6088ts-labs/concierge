from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from concierge.loggers import get_logger
from concierge.todo.infrastructure.web.exception_handlers import register_exception_handlers
from concierge.todo.infrastructure.web.routes import router

logger = get_logger("concierge.todo")


def create_app() -> FastAPI:
    app = FastAPI(title="Todo API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(router)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("Initialized Todo FastAPI app")
    return app


def start() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    start()
