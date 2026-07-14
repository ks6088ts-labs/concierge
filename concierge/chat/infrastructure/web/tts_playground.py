from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DEFAULT_CONFIG: dict[str, Any] = {
    "title": "つたえるボタン",
    "lang": "ja-JP",
    "rate": 1.0,
    "pitch": 1.0,
    "items": [
        {"id": "thanks", "label": "ありがとう", "emoji": "🙏", "text": "ありがとう"},
        {"id": "love", "label": "大好きだよ", "emoji": "❤️", "text": "大好きだよ"},
        {"id": "want_do", "label": "これをやりたい", "emoji": "✨", "text": "これをやりたい"},
        {"id": "want_together", "label": "一緒にやりたい", "emoji": "🤝", "text": "一緒にやりたい"},
        {"id": "tasty", "label": "おいしい", "emoji": "🍴", "text": "おいしい"},
        {"id": "happy", "label": "うれしい", "emoji": "😊", "text": "うれしい"},
        {"id": "hungry", "label": "お腹がすいた", "emoji": "🍙", "text": "お腹がすいた"},
        {"id": "toilet", "label": "トイレに行きたい", "emoji": "🚻", "text": "トイレに行きたい"},
    ],
}

INDEX_HTML = (Path(__file__).parent / "static" / "tts_playground.html").read_text(encoding="utf-8")


def create_tts_playground_app() -> FastAPI:
    config = DEFAULT_CONFIG
    app = FastAPI(title=config.get("title", "voice-buttons"))
    html = INDEX_HTML.replace("__TITLE__", config.get("title", "つたえるボタン"))

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(html)

    @app.get("/config")
    def get_config() -> JSONResponse:
        return JSONResponse(config)

    return app
