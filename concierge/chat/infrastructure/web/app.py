from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from concierge.chat.infrastructure.web.exception_handlers import register_exception_handlers
from concierge.chat.infrastructure.web.routes import router
from concierge.loggers import get_logger

logger = get_logger("concierge.chat")


def create_app() -> FastAPI:
    app = FastAPI(title="Chat API", version="0.1.0")
    static_dir = Path(__file__).parent / "static"

    register_exception_handlers(app)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    logger.info("Initialized Chat FastAPI app")
    return app


def start() -> None:
    uvicorn.run("concierge.chat.infrastructure.web.app:create_app", factory=True, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    start()
