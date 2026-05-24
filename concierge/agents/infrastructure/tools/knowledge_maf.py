from __future__ import annotations

from collections.abc import Callable
from typing import Any

from concierge.agents.infrastructure.tools.knowledge import search_knowledge_chunks
from concierge.loggers import get_logger
from concierge.settings.agents_knowledge import AgentsKnowledgeSettings, AgentsKnowledgeToolConfig

logger = get_logger(__name__)
_MAX_DESCRIPTION_LEN = 400


def build_knowledge_maf_tool_builders(
    settings: AgentsKnowledgeSettings,
) -> list[Callable[[dict[str, Any]], Any]]:
    return [_build_maf_builder(config) for config in settings.configured_tools()]


def _build_maf_builder(config: AgentsKnowledgeToolConfig) -> Callable[[dict[str, Any]], Any]:
    if len(config.description) > _MAX_DESCRIPTION_LEN:
        logger.warning(
            "knowledge tool description is long: tool_name=%s length=%s",
            config.name,
            len(config.description),
        )

    def _build(_side_outputs: dict[str, Any]) -> Any:
        from agent_framework import tool

        def _invoke(query: str, k: int | None = None) -> str:
            return search_knowledge_chunks(config=config, query=query, k=k, tool_name=config.name)

        _invoke.__name__ = config.name
        _invoke.__doc__ = config.description
        return tool(_invoke)

    return _build
