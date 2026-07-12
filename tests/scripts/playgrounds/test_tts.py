from __future__ import annotations

from fastapi.testclient import TestClient

from scripts.playgrounds.tts import DEFAULT_CONFIG, create_app


def test_tts_app_serves_custom_text_input() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="custom-form"' in response.text
    assert 'id="custom-text"' in response.text
    assert 'id="custom-play"' in response.text
    assert "handleCustomSubmit" in response.text


def test_tts_config_response_is_unchanged_by_custom_input() -> None:
    client = TestClient(create_app())

    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == DEFAULT_CONFIG
