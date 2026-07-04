from __future__ import annotations

from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from concierge.chat.infrastructure.ai.factory import ChatbotNotConfiguredError, create_realtime_responder
from concierge.chat.infrastructure.web.exception_handlers import register_exception_handlers
from concierge.chat.infrastructure.web.routes import router
from concierge.loggers import get_logger
from concierge.observability import bootstrap_from_env
from concierge.settings import get_chat_settings

logger = get_logger("concierge.chat")


def create_app() -> FastAPI:
    # Populate ``os.environ`` from a local ``.env`` file. ``pydantic-settings``
    # reads ``.env`` directly for our own settings classes, but third-party
    # libraries such as ``langchain-azure-ai`` look up configuration (for
    # example ``AZURE_AI_PROJECT_ENDPOINT``) via ``os.environ``. Existing
    # process env vars take precedence (``override=False`` by default).
    load_dotenv()
    bootstrap_from_env("concierge-chat")

    app = FastAPI(title="Chat API", version="0.1.0")
    static_dir = Path(__file__).parent / "static"

    register_exception_handlers(app)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/capabilities", tags=["health"])
    def capabilities() -> dict[str, bool]:
        """Return feature toggles the web UI uses to enable/disable controls.

        ``realtime`` reflects whether ``AZURE_AI_PROJECT_ENDPOINT_REALTIME`` is
        configured — the client uses it to show/hide the voice call button.
        """
        try:
            create_realtime_responder()
            realtime_enabled = True
        except ChatbotNotConfiguredError:
            realtime_enabled = False
        return {"realtime": realtime_enabled}

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/accessible", include_in_schema=False)
    def accessible_index() -> FileResponse:
        """Serve the minimal deafblind accessibility UI.

        A stripped-down, single-button voice page whose only visible content is
        the dialogue text (in an ARIA live region) so a BrailleSense web reader
        reaches the conversation immediately without wading through chrome.
        """
        return FileResponse(static_dir / "accessible.html")

    @app.get("/accessible/config", tags=["health"])
    def accessible_config() -> dict[str, object]:
        """Return runtime config the accessible UI needs on load.

        ``realtime`` mirrors ``/capabilities`` (voice requires the realtime
        endpoint). ``tts_rate`` is the configured browser Text-to-Speech rate
        (the realtime voice itself cannot be rate-controlled).
        """
        try:
            create_realtime_responder()
            realtime_enabled = True
        except ChatbotNotConfiguredError:
            realtime_enabled = False
        return {"realtime": realtime_enabled, "tts_rate": get_chat_settings().accessible_tts_rate}

    @app.get("/realtime", include_in_schema=False)
    def realtime_index() -> RedirectResponse:
        # The dedicated realtime UI has been merged into ``/``. Keep this route
        # so existing bookmarks and docs continue to work.
        return RedirectResponse(url="/", status_code=301)

    logger.info("Initialized Chat FastAPI app")
    return app


def start() -> None:
    uvicorn.run("concierge.chat.infrastructure.web.app:create_app", factory=True, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    start()
