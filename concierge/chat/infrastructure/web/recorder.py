from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DEFAULT_CONFIG: dict[str, str] = {
    "title": "録音アプリ",
}

INDEX_HTML = (Path(__file__).parent / "static" / "recorder.html").read_text(encoding="utf-8")


def create_recorder_app() -> FastAPI:
    config = DEFAULT_CONFIG
    app = FastAPI(title=config.get("title", "recorder"))
    html = INDEX_HTML.replace("__TITLE__", config.get("title", "録音アプリ"))

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(html)

    @app.get("/config")
    def get_config() -> JSONResponse:
        return JSONResponse(config)

    return app
