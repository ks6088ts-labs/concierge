from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from concierge.agents.infrastructure.tools import web_fetch
from concierge.agents.infrastructure.tools.web_fetch import WebFetchConfig, fetch_webpage
from concierge.agents.infrastructure.tools.web_fetch_tool import (
    build_web_fetch_config,
    build_web_langchain_tool_builders,
    parse_enabled_web_tools,
)
from concierge.settings.agents import AgentsSettings

_ARTICLE_HTML = (
    "<html><head><title>Hello &amp; World</title></head><body><article>"
    "<h1>Heading</h1>"
    "<p>This is the first meaningful paragraph with enough text to be extracted reliably.</p>"
    "<p>Second paragraph also has a good amount of content so extraction succeeds nicely.</p>"
    "</article></body></html>"
)

Handler = Callable[[httpx.Request], httpx.Response]


def _install_transport(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    def _factory(config: WebFetchConfig) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
            headers={"User-Agent": config.user_agent},
        )

    monkeypatch.setattr(web_fetch, "_build_client", _factory)


def _local_config(
    *,
    max_bytes: int = 3_000_000,
    max_content_chars: int = 8000,
) -> WebFetchConfig:
    # allow_private_ips skips DNS resolution so tests never touch the network.
    return WebFetchConfig(
        allow_private_ips=True,
        max_bytes=max_bytes,
        max_content_chars=max_content_chars,
    )


def test_fetch_webpage_extracts_title_and_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: httpx.Response(200, text=_ARTICLE_HTML))

    payload = json.loads(
        fetch_webpage(config=_local_config(), url="http://example.com/a", max_chars=None, tool_name="fetch_webpage")
    )

    assert payload["title"] == "Hello & World"
    assert payload["status_code"] == 200
    assert payload["truncated"] is False
    assert "first meaningful paragraph" in payload["content"]
    assert "error" not in payload


def test_fetch_webpage_truncates_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: httpx.Response(200, text=_ARTICLE_HTML))

    payload = json.loads(
        fetch_webpage(config=_local_config(), url="http://example.com/a", max_chars=10, tool_name="fetch_webpage")
    )

    assert payload["truncated"] is True
    assert payload["content"].endswith("…")
    assert len(payload["content"]) == 11


def test_fetch_webpage_rejects_non_textual_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(
        monkeypatch,
        lambda request: httpx.Response(200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"}),
    )

    payload = json.loads(
        fetch_webpage(config=_local_config(), url="http://example.com/f.pdf", max_chars=None, tool_name="fetch_webpage")
    )

    assert "unsupported content type" in payload["message"]
    assert payload["content"] == ""


def test_fetch_webpage_caps_response_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    big_html = "<html><body>" + ("<p>spam</p>" * 5000) + "</body></html>"
    _install_transport(monkeypatch, lambda request: httpx.Response(200, text=big_html))

    payload = json.loads(
        fetch_webpage(
            config=_local_config(max_bytes=200), url="http://example.com/big", max_chars=None, tool_name="fetch_webpage"
        )
    )

    assert payload["status_code"] == 200
    assert payload["truncated"] is True
    assert "error" not in payload


def test_fetch_webpage_rejects_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: httpx.Response(404, text="<html><body>missing</body></html>"))

    payload = json.loads(
        fetch_webpage(
            config=_local_config(), url="http://example.com/missing", max_chars=None, tool_name="fetch_webpage"
        )
    )

    assert "HTTP 404" in payload["error"]


def test_fetch_webpage_enforces_redirect_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(
        monkeypatch,
        lambda request: httpx.Response(302, headers={"location": "http://example.com/again"}),
    )

    payload = json.loads(
        fetch_webpage(
            config=_local_config(),
            url="http://example.com/start",
            max_chars=None,
            tool_name="fetch_webpage",
        )
    )

    assert "too many redirects" in payload["error"]


def test_fetch_webpage_follows_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "http://example.com/final"})
        return httpx.Response(200, text=_ARTICLE_HTML)

    _install_transport(monkeypatch, handler)

    payload = json.loads(
        fetch_webpage(config=_local_config(), url="http://example.com/start", max_chars=None, tool_name="fetch_webpage")
    )

    assert payload["url"] == "http://example.com/final"
    assert payload["title"] == "Hello & World"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ],
)
def test_fetch_webpage_rejects_non_http_scheme(url: str) -> None:
    payload = json.loads(fetch_webpage(config=WebFetchConfig(), url=url, max_chars=None, tool_name="fetch_webpage"))
    assert "unsupported URL scheme" in payload["error"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost/",
        "http://192.168.0.1/",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ],
)
def test_fetch_webpage_blocks_ssrf_targets(url: str) -> None:
    # allow_private_ips defaults to False -> internal/private hosts are rejected
    # by DNS/IP validation before any request is made.
    payload = json.loads(fetch_webpage(config=WebFetchConfig(), url=url, max_chars=None, tool_name="fetch_webpage"))
    assert "error" in payload
    assert "non-public" in payload["error"] or "could not resolve" in payload["error"]


def test_fetch_webpage_blocks_redirect_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list:
        try:
            import ipaddress

            ipaddress.ip_address(host)
            addr = host
        except ValueError:
            addr = "93.184.216.34"  # public IP for the initial hop
        return [(2, 1, 6, "", (addr, port or 0))]

    monkeypatch.setattr(web_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    _install_transport(
        monkeypatch,
        lambda request: httpx.Response(302, headers={"location": "http://127.0.0.1/secret"}),
    )

    payload = json.loads(
        fetch_webpage(
            config=WebFetchConfig(max_redirects=3),
            url="http://example.com/start",
            max_chars=None,
            tool_name="fetch_webpage",
        )
    )

    assert "non-public" in payload["error"]


def test_fetch_webpage_enforces_domain_denylist() -> None:
    config = WebFetchConfig(allow_private_ips=True, denied_domains=("evil.example",))
    payload = json.loads(
        fetch_webpage(config=config, url="http://sub.evil.example/x", max_chars=None, tool_name="fetch_webpage")
    )
    assert "blocked by policy" in payload["error"]


def test_fetch_webpage_enforces_domain_allowlist() -> None:
    config = WebFetchConfig(allow_private_ips=True, allowed_domains=("trusted.example",))
    payload = json.loads(
        fetch_webpage(config=config, url="http://other.example/x", max_chars=None, tool_name="fetch_webpage")
    )
    assert "not in the allowlist" in payload["error"]


def test_langchain_builder_produces_fetch_webpage_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: httpx.Response(200, text=_ARTICLE_HTML))
    builders = build_web_langchain_tool_builders(_local_config(), "fetch_webpage")

    assert len(builders) == 1
    tool = builders[0]({})
    assert tool.name == "fetch_webpage"

    payload = json.loads(tool.invoke({"url": "http://example.com/a"}))
    assert payload["title"] == "Hello & World"


def test_langchain_builder_disabled_returns_empty() -> None:
    assert build_web_langchain_tool_builders(_local_config(), "") == []


def test_parse_enabled_web_tools_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        parse_enabled_web_tools("bogus_tool")


def test_build_web_fetch_config_maps_settings() -> None:
    settings = AgentsSettings(
        _env_file=None,  # ty: ignore[unknown-argument]
        web_fetch_timeout_seconds=7,
        web_fetch_deny_domains="a.example, b.example",
        web_fetch_max_redirects=2,
    )

    config = build_web_fetch_config(settings)

    assert config.timeout_seconds == 7
    assert config.denied_domains == ("a.example", "b.example")
    assert config.max_redirects == 2
