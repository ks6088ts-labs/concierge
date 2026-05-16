from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from concierge.cloud_agent.infrastructure.web.exception_handlers import register_exception_handlers
from concierge.cloud_agent.infrastructure.web.routes import router
from concierge.loggers import get_logger

logger = get_logger("concierge.cloud_agent")


def create_app() -> FastAPI:
    app = FastAPI(title="Cloud Agent API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(router)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("Initialized Cloud Agent FastAPI app")
    return app


def start() -> None:
    uvicorn.run("concierge.cloud_agent.infrastructure.web.app:create_app", factory=True, host="0.0.0.0", port=8081)


if __name__ == "__main__":
    start()
