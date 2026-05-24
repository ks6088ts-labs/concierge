from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool

from concierge.agents.infrastructure.tools.knowledge import KnowledgeSearchParams, search_knowledge_chunks
from concierge.loggers import get_logger
from concierge.settings.agents_knowledge import AgentsKnowledgeSettings, AgentsKnowledgeToolConfig

logger = get_logger(__name__)
_MAX_DESCRIPTION_LEN = 400


def build_knowledge_langchain_tool_builders(
    settings: AgentsKnowledgeSettings,
) -> list[Callable[[dict[str, Any]], Any]]:
    return [_build_langchain_builder(config) for config in settings.configured_tools()]


def _build_langchain_builder(config: AgentsKnowledgeToolConfig) -> Callable[[dict[str, Any]], Any]:
    if len(config.description) > _MAX_DESCRIPTION_LEN:
        logger.warning(
            "knowledge tool description is long: tool_name=%s length=%s",
            config.name,
            len(config.description),
        )

    def _build(_side_outputs: dict[str, Any]) -> Any:
        def _invoke(query: str, k: int | None = None) -> str:
            return search_knowledge_chunks(config=config, query=query, k=k, tool_name=config.name)

        return StructuredTool.from_function(
            func=_invoke,
            name=config.name,
            description=config.description,
            args_schema=KnowledgeSearchParams,
        )

    return _build
