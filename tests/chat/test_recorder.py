from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.chat.infrastructure.web.app import create_app
from concierge.chat.infrastructure.web.recorder import DEFAULT_CONFIG


@pytest.mark.anyio
async def test_chat_web_serves_recorder() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        redirect = await client.get("/recorder")
        assert redirect.status_code == 307
        assert redirect.headers["location"] == "/recorder/"

        page = await client.get("/recorder/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert 'id="btn-record"' in page.text
        assert 'id="btn-stop"' in page.text
        assert 'id="recordings-list"' in page.text
        assert 'MediaRecorder' in page.text

        config = await client.get("/recorder/config")
        assert config.status_code == 200
        assert config.json() == DEFAULT_CONFIG

        chat_page = await client.get("/")
        assert chat_page.status_code == 200
        assert 'id="btn-record"' not in chat_page.text
