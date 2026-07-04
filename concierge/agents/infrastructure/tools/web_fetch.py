"""SDK-independent single-URL web page fetching core for agent tools.

Fetches ONE page over HTTP(S) and returns its main textual content as Markdown.
This is intentionally *not* a crawler: it does not follow in-page links, run
JavaScript, or search the web. Static HTML only.

Security: the URL is supplied by the LLM/user, so this is a classic SSRF sink.
Before every request (and every redirect hop) the target host is resolved and
rejected when it points at a non-public address (loopback, private, link-local,
cloud-metadata, ...). Only ``http``/``https`` schemes are allowed, responses are
size-capped, and only textual content types are parsed.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from html import unescape
from time import perf_counter
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura
from pydantic import BaseModel, Field

from concierge.agents.infrastructure.tools.exceptions import WebFetchError
from concierge.loggers import get_logger

logger = get_logger(__name__)

WEB_FETCH_TOOL_NAME = "fetch_webpage"

_ELLIPSIS = "…"
_MAX_CONTENT_CHARS = 20000
_MAX_TITLE_CHARS = 300
_ALLOWED_SCHEMES = ("http", "https")
_DEFAULT_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5"
_TEXTUAL_APPLICATION_TYPES = frozenset({"application/xhtml+xml", "application/xml", "application/rss+xml"})
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_WHITESPACE_RE = re.compile(r"\s+")


class FetchWebpageParams(BaseModel):
    url: str = Field(description="Absolute http(s) URL of the web page to fetch")
    max_chars: int | None = Field(
        default=None,
        ge=1,
        le=_MAX_CONTENT_CHARS,
        description="Maximum characters of extracted content to return; None uses the tool default",
    )


@dataclass(frozen=True)
class WebFetchConfig:
    timeout_seconds: int = 10
    max_bytes: int = 3_000_000
    max_content_chars: int = 8000
    user_agent: str = "conciergebot/1.0"
    allowed_domains: tuple[str, ...] = ()
    denied_domains: tuple[str, ...] = ()
    max_redirects: int = 5
    allow_private_ips: bool = False


@dataclass(frozen=True)
class _FetchResult:
    final_url: str
    html: str
    content_type: str
    status_code: int
    textual: bool
    body_truncated: bool = False


def fetch_webpage(
    *,
    config: WebFetchConfig,
    url: str,
    max_chars: int | None,
    tool_name: str,
) -> str:
    """Fetch ``url`` and return a compact JSON string with the page content.

    On success the payload contains ``url`` (final URL after redirects),
    ``title``, ``content`` (Markdown, possibly truncated), ``truncated`` and
    ``status_code``. Failures (including SSRF rejections) are swallowed and
    returned as ``{"error": ..., "url": ...}`` so the model can react gracefully.
    """
    started_at = perf_counter()
    resolved_max = _resolve_max_chars(max_chars, config.max_content_chars)
    try:
        result = _fetch(config, url)
        if not result.textual:
            payload: dict[str, Any] = {
                "url": result.final_url,
                "title": "",
                "content": "",
                "status_code": result.status_code,
                "message": f"unsupported content type: {result.content_type or 'unknown'}",
            }
            _log_summary(
                tool_name=tool_name,
                url=result.final_url,
                status_code=result.status_code,
                content_chars=0,
                started_at=started_at,
            )
            return _compact_json(payload)

        title = _extract_title(result.html)
        content = _extract_content(result.html)
        content, content_truncated = _truncate_content(content, max_chars=resolved_max)
        payload = {
            "url": result.final_url,
            "title": title,
            "content": content,
            "truncated": content_truncated or result.body_truncated,
            "status_code": result.status_code,
        }
        if not content:
            payload["message"] = "No extractable content."
        _log_summary(
            tool_name=tool_name,
            url=result.final_url,
            status_code=result.status_code,
            content_chars=len(content),
            started_at=started_at,
        )
        return _compact_json(payload)
    except WebFetchError as exc:
        logger.info("operation=web_fetch_rejected tool_name=%s url=%s reason=%s", tool_name, url, exc)
        return _compact_json({"error": str(exc), "url": url})
    except httpx.HTTPError as exc:
        logger.info("operation=web_fetch_http_error tool_name=%s url=%s error=%s", tool_name, url, type(exc).__name__)
        return _compact_json({"error": f"web fetch failed: {type(exc).__name__}", "url": url})
    except Exception as exc:  # noqa: BLE001
        logger.exception("operation=web_fetch_failed tool_name=%s url=%s", tool_name, url)
        return _compact_json({"error": f"web fetch failed: {type(exc).__name__}", "url": url})


def _build_client(config: WebFetchConfig) -> httpx.Client:
    """Create the HTTP client. Isolated so tests can inject a mock transport."""
    return httpx.Client(
        follow_redirects=False,
        timeout=config.timeout_seconds,
        headers={"User-Agent": config.user_agent, "Accept": _DEFAULT_ACCEPT},
    )


def _fetch(config: WebFetchConfig, url: str) -> _FetchResult:
    client = _build_client(config)
    with client:
        current = url
        redirects_followed = 0
        while True:
            host, port = _validate_url(current)
            _check_domain_policy(host, config)
            _check_host_is_public(host, port, allow_private_ips=config.allow_private_ips)
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    if redirects_followed >= config.max_redirects:
                        raise WebFetchError(f"too many redirects (>{config.max_redirects})")
                    location = response.headers.get("location")
                    if not location:
                        raise WebFetchError("redirect response is missing a Location header")
                    redirects_followed += 1
                    current = urljoin(current, location)
                    continue
                if response.status_code >= 400:
                    raise WebFetchError(f"HTTP {response.status_code} when fetching URL")
                content_type = response.headers.get("content-type", "")
                if not _is_textual(content_type):
                    return _FetchResult(
                        final_url=str(response.url),
                        html="",
                        content_type=content_type,
                        status_code=response.status_code,
                        textual=False,
                    )
                raw, body_truncated = _read_capped(response, config.max_bytes)
                html = raw.decode(response.encoding or "utf-8", errors="replace")
                return _FetchResult(
                    final_url=str(response.url),
                    html=html,
                    content_type=content_type,
                    status_code=response.status_code,
                    textual=True,
                    body_truncated=body_truncated,
                )


def _read_capped(response: httpx.Response, max_bytes: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        chunks.append(chunk)
        total += len(chunk)
        if total >= max_bytes:
            break
    raw = b"".join(chunks)
    return raw[:max_bytes], total >= max_bytes


def _validate_url(url: str) -> tuple[str, int | None]:
    parts = urlsplit(url)
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise WebFetchError(f"unsupported URL scheme: {parts.scheme or '(none)'!r}")
    if not parts.hostname:
        raise WebFetchError("URL has no host")
    try:
        port = parts.port
    except ValueError as exc:
        raise WebFetchError("URL has an invalid port") from exc
    return parts.hostname, port


def _check_domain_policy(hostname: str, config: WebFetchConfig) -> None:
    host = hostname.lower()
    if config.denied_domains and _matches_any(host, config.denied_domains):
        raise WebFetchError(f"domain is blocked by policy: {host}")
    if config.allowed_domains and not _matches_any(host, config.allowed_domains):
        raise WebFetchError(f"domain is not in the allowlist: {host}")


def _matches_any(host: str, domains: tuple[str, ...]) -> bool:
    for domain in domains:
        candidate = domain.strip().lower().lstrip(".")
        if candidate and (host == candidate or host.endswith(f".{candidate}")):
            return True
    return False


def _check_host_is_public(hostname: str, port: int | None, *, allow_private_ips: bool) -> None:
    if allow_private_ips:
        return
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise WebFetchError(f"could not resolve host: {hostname}") from exc
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if not ip.is_global:
            raise WebFetchError(f"refusing to fetch non-public address: {ip}")


def _is_textual(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith("text/") or media_type in _TEXTUAL_APPLICATION_TYPES


def _extract_content(html: str) -> str:
    try:
        extracted = trafilatura.extract(
            html,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
        )
    except Exception:  # noqa: BLE001
        logger.exception("operation=web_fetch_extract_failed")
        return ""
    return extracted or ""


def _extract_title(html: str) -> str:
    match = _TITLE_RE.search(html)
    if not match:
        return ""
    title = _WHITESPACE_RE.sub(" ", unescape(match.group(1))).strip()
    return title[:_MAX_TITLE_CHARS]


def _resolve_max_chars(max_chars: int | None, default: int) -> int:
    value = max_chars if max_chars is not None else default
    if value < 1:
        return 1
    return min(value, _MAX_CONTENT_CHARS)


def _truncate_content(content: str, *, max_chars: int) -> tuple[str, bool]:
    if len(content) <= max_chars:
        return content, False
    return f"{content[:max_chars]}{_ELLIPSIS}", True


def _log_summary(*, tool_name: str, url: str, status_code: int, content_chars: int, started_at: float) -> None:
    latency_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "operation=web_fetch tool_name=%s url=%s status_code=%s content_chars=%s latency_ms=%s",
        tool_name,
        url,
        status_code,
        content_chars,
        latency_ms,
    )


def _compact_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
