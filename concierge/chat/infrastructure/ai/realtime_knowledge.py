from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import ValidationError

from concierge.agents.infrastructure.tools.knowledge import KnowledgeSearchParams, search_knowledge_chunks
from concierge.chat.application.use_cases import RealtimeToolExecutor
from concierge.settings import get_agents_knowledge_settings
from concierge.settings.agents_knowledge import AgentsKnowledgeToolConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RealtimeKnowledgeToolAdapter:
    config: AgentsKnowledgeToolConfig

    def tool_definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.config.name,
            "description": self.config.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "k": {
                        "type": ["integer", "null"],
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Number of chunks to return; null falls back to tool default top_k",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        }

    def execute(self, tool_name: str, arguments: dict[str, object]) -> str | None:
        if tool_name != self.config.name:
            return None
        try:
            params = KnowledgeSearchParams.model_validate(arguments)
        except ValidationError as exc:
            return json.dumps(
                {
                    "error": "invalid knowledge tool arguments",
                    "details": exc.errors(include_url=False),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )

        return search_knowledge_chunks(
            config=self.config,
            query=params.query,
            k=params.k,
            tool_name=self.config.name,
        )


@lru_cache
def get_realtime_knowledge_tool_adapter() -> RealtimeKnowledgeToolAdapter | None:
    settings = get_agents_knowledge_settings()
    try:
        configs = settings.configured_tools()
    except ValueError:
        logger.exception("Failed to resolve AGENTS_KNOWLEDGE settings; realtime tool-calling is disabled")
        return None

    if not configs:
        return None
    if len(configs) > 1:
        logger.info(
            "Realtime voice tool-calling currently supports one knowledge tool; using the first configured tool: %s",
            configs[0].name,
        )
    return RealtimeKnowledgeToolAdapter(config=configs[0])


def get_realtime_tool_definitions() -> list[dict[str, Any]]:
    adapter = get_realtime_knowledge_tool_adapter()
    if adapter is None:
        return []
    return [adapter.tool_definition()]


def get_realtime_tool_executor() -> RealtimeToolExecutor | None:
    adapter = get_realtime_knowledge_tool_adapter()
    if adapter is None:
        return None
    return adapter.execute
