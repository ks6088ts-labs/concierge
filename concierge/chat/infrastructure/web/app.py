from __future__ import annotations

from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from concierge.chat.infrastructure.web.exception_handlers import register_exception_handlers
from concierge.chat.infrastructure.web.routes import router
from concierge.loggers import get_logger

logger = get_logger("concierge.chat")


def create_app() -> FastAPI:
    # Populate ``os.environ`` from a local ``.env`` file. ``pydantic-settings``
    # reads ``.env`` directly for our own settings classes, but third-party
    # libraries such as ``langchain-azure-ai`` look up configuration (for
    # example ``AZURE_AI_PROJECT_ENDPOINT``) via ``os.environ``. Existing
    # process env vars take precedence (``override=False`` by default).
    load_dotenv()

    app = FastAPI(title="Chat API", version="0.1.0")
    static_dir = Path(__file__).parent / "static"
    static_realtime_dir = Path(__file__).parent / "static_realtime"

    register_exception_handlers(app)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    if static_realtime_dir.is_dir():
        app.mount("/realtime-static", StaticFiles(directory=static_realtime_dir), name="static_realtime")

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/realtime", include_in_schema=False)
    def realtime_index() -> FileResponse:
        return FileResponse(static_realtime_dir / "index.html")

    logger.info("Initialized Chat FastAPI app")
    return app


def start() -> None:
    uvicorn.run("concierge.chat.infrastructure.web.app:create_app", factory=True, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    start()
