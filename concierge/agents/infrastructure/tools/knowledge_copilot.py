from __future__ import annotations

from collections.abc import Callable
from typing import Any

from copilot import define_tool

from concierge.agents.infrastructure.tools.knowledge import KnowledgeSearchParams, search_knowledge_chunks
from concierge.loggers import get_logger
from concierge.settings.agents_knowledge import AgentsKnowledgeSettings, AgentsKnowledgeToolConfig

logger = get_logger(__name__)
_MAX_DESCRIPTION_LEN = 400


def build_knowledge_copilot_sdk_tool_builders(
    settings: AgentsKnowledgeSettings,
) -> list[Callable[[dict[str, Any]], Any]]:
    return [_build_copilot_builder(config) for config in settings.configured_tools()]


def _build_copilot_builder(config: AgentsKnowledgeToolConfig) -> Callable[[dict[str, Any]], Any]:
    if len(config.description) > _MAX_DESCRIPTION_LEN:
        logger.warning(
            "knowledge tool description is long: tool_name=%s length=%s",
            config.name,
            len(config.description),
        )

    def _build(_side_outputs: dict[str, Any]) -> Any:
        @define_tool(
            name=config.name,
            description=config.description,
            skip_permission=True,
        )
        def knowledge_search_tool(params: KnowledgeSearchParams) -> str:
            return search_knowledge_chunks(
                config=config,
                query=params.query,
                k=params.k,
                tool_name=config.name,
            )

        return knowledge_search_tool

    return _build
