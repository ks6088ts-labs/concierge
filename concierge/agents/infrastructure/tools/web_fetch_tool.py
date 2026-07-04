"""Web-fetch tool builders for LangChain, MAF, and Copilot SDK.

All three adapters wrap the same :func:`fetch_webpage` core so every agent
surface (text agents and the realtime/voice agent) shares one implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from concierge.agents.infrastructure.tools.web_fetch import (
    WEB_FETCH_TOOL_NAME,
    FetchWebpageParams,
    WebFetchConfig,
    fetch_webpage,
)
from concierge.settings.agents import AgentsSettings

WEB_TOOL_NAMES: tuple[str, ...] = (WEB_FETCH_TOOL_NAME,)

_DESCRIPTION = (
    "Fetch a single web page by its http(s) URL and return the main text content "
    "as Markdown together with the page title. Use this whenever the user provides "
    "a URL or asks you to read, open, summarize, or check a specific web page. "
    "It fetches exactly one page (no crawling, no web search, no JavaScript rendering)."
)


def parse_enabled_web_tools(value: str | Sequence[str]) -> list[str]:
    if isinstance(value, str):
        enabled = [name.strip() for name in value.split(",") if name.strip()]
    else:
        enabled = [name.strip() for name in value if name.strip()]

    unknown = sorted({name for name in enabled if name not in WEB_TOOL_NAMES})
    if unknown:
        raise ValueError(f"Unknown web tool(s): {', '.join(unknown)}")
    return enabled


def build_web_fetch_config(settings: AgentsSettings) -> WebFetchConfig:
    return WebFetchConfig(
        timeout_seconds=settings.web_fetch_timeout_seconds,
        max_bytes=settings.web_fetch_max_bytes,
        max_content_chars=settings.web_fetch_max_content_chars,
        user_agent=settings.web_fetch_user_agent,
        allowed_domains=_parse_domains(settings.web_fetch_allow_domains),
        denied_domains=_parse_domains(settings.web_fetch_deny_domains),
        max_redirects=settings.web_fetch_max_redirects,
        allow_private_ips=settings.web_fetch_allow_private_ips,
    )


def build_web_langchain_tool_builders(
    config: WebFetchConfig,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    if WEB_FETCH_TOOL_NAME not in parse_enabled_web_tools(enabled):
        return []
    return [_build_langchain_builder(config)]


def build_web_maf_tool_builders(
    config: WebFetchConfig,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    if WEB_FETCH_TOOL_NAME not in parse_enabled_web_tools(enabled):
        return []
    return [_build_maf_builder(config)]


def build_web_copilot_sdk_tool_builders(
    config: WebFetchConfig,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    if WEB_FETCH_TOOL_NAME not in parse_enabled_web_tools(enabled):
        return []
    return [_build_copilot_builder(config)]


def _build_langchain_builder(config: WebFetchConfig) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from langchain_core.tools import StructuredTool

        def _invoke(url: str, max_chars: int | None = None) -> str:
            return fetch_webpage(config=config, url=url, max_chars=max_chars, tool_name=WEB_FETCH_TOOL_NAME)

        return StructuredTool.from_function(
            func=_invoke,
            name=WEB_FETCH_TOOL_NAME,
            description=_DESCRIPTION,
            args_schema=FetchWebpageParams,
        )

    return _build


def _build_maf_builder(config: WebFetchConfig) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from agent_framework import tool

        def _invoke(url: str, max_chars: int | None = None) -> str:
            return fetch_webpage(config=config, url=url, max_chars=max_chars, tool_name=WEB_FETCH_TOOL_NAME)

        _invoke.__name__ = WEB_FETCH_TOOL_NAME
        _invoke.__doc__ = _DESCRIPTION
        return tool(_invoke)

    return _build


def _build_copilot_builder(config: WebFetchConfig) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from copilot import define_tool

        @define_tool(
            name=WEB_FETCH_TOOL_NAME,
            description=_DESCRIPTION,
            skip_permission=True,
        )
        def fetch_webpage_tool(params: FetchWebpageParams) -> str:
            return fetch_webpage(
                config=config,
                url=params.url,
                max_chars=params.max_chars,
                tool_name=WEB_FETCH_TOOL_NAME,
            )

        return fetch_webpage_tool

    return _build


def _parse_domains(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())
