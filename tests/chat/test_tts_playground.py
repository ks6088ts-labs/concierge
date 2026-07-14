from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.chat.infrastructure.web.app import create_app
from concierge.chat.infrastructure.web.tts_playground import DEFAULT_CONFIG


@pytest.mark.anyio
async def test_chat_web_serves_tts_playground() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        redirect = await client.get("/ttsplayground")
        assert redirect.status_code == 307
        assert redirect.headers["location"] == "/ttsplayground/"

        page = await client.get("/ttsplayground/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert 'id="custom-form"' in page.text
        assert 'id="custom-text"' in page.text
        assert 'id="custom-play"' in page.text
        assert 'fetch("config")' in page.text
        assert '"voices/"' in page.text

        config = await client.get("/ttsplayground/config")
        assert config.status_code == 200
        assert config.json() == DEFAULT_CONFIG

        missing_voice = await client.get("/ttsplayground/voices/missing.mp3")
        assert missing_voice.status_code == 404

        chat_page = await client.get("/")
        assert chat_page.status_code == 200
        assert 'id="custom-form"' not in chat_page.text
