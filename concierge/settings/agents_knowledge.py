from __future__ import annotations

import os
import re
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from concierge.settings.knowledge import KnowledgeTarget

KNOWLEDGE_COLLECTION_FIELD = "collection"
_DEFAULT_TOP_K = 4
_DEFAULT_MAX_CHARS = 1200
_MAX_TOP_K = 20
_MAX_TOOL_NAME_LEN = 50
_MAX_DESCRIPTION_LEN = 400
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_RESERVED_TOOL_NAMES = {
    "echo",
    "generate_image_tool",
    "read_file",
    "list_directory",
    "file_search",
    "write_file",
    "copy_file",
    "move_file",
    "delete_file",
    "shell_exec",
}


class AgentsKnowledgeToolConfig(BaseModel):
    name: str
    collection: str
    description: str
    top_k: int = Field(default=_DEFAULT_TOP_K, ge=1, le=_MAX_TOP_K)
    max_chars: int = Field(default=_DEFAULT_MAX_CHARS, ge=1)
    target: KnowledgeTarget = KnowledgeTarget.DOCKER


class AgentsKnowledgeSettings(BaseSettings):
    tools: str = ""
    # PostgreSQL target backing every configured knowledge tool: ``docker``
    # (local pgvector via ``POSTGRES_*``) or ``azure`` (Azure Database for
    # PostgreSQL via ``AZURE_*``). Override with ``AGENTS_KNOWLEDGE__TARGET``.
    target: KnowledgeTarget = KnowledgeTarget.DOCKER

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="AGENTS_KNOWLEDGE__",
        extra="ignore",
    )

    def configured_tools(self) -> list[AgentsKnowledgeToolConfig]:
        names = self._parse_tool_names(self.tools)
        if not names:
            return []

        env_map = {key.lower(): value for key, value in os.environ.items()}
        configs: list[AgentsKnowledgeToolConfig] = []
        for name in names:
            key_prefix = f"agents_knowledge__{name}__"
            collection = env_map.get(f"{key_prefix}{KNOWLEDGE_COLLECTION_FIELD}")
            if not collection:
                raise ValueError(f"AGENTS_KNOWLEDGE__{name.upper()}__{KNOWLEDGE_COLLECTION_FIELD.upper()} is required")

            top_k = self._parse_optional_int(
                env_map.get(f"{key_prefix}top_k"),
                default=_DEFAULT_TOP_K,
                field_name=f"AGENTS_KNOWLEDGE__{name.upper()}__TOP_K",
            )
            max_chars = self._parse_optional_int(
                env_map.get(f"{key_prefix}max_chars"),
                default=_DEFAULT_MAX_CHARS,
                field_name=f"AGENTS_KNOWLEDGE__{name.upper()}__MAX_CHARS",
                min_value=1,
            )
            description = env_map.get(f"{key_prefix}description") or self._default_description(collection, top_k)
            configs.append(
                AgentsKnowledgeToolConfig(
                    name=name,
                    collection=collection,
                    description=description,
                    top_k=top_k,
                    max_chars=max_chars,
                    target=self.target,
                )
            )
        return configs

    @staticmethod
    def _default_description(collection: str, top_k: int) -> str:
        return (
            f"Search the '{collection}' knowledge collection by semantic similarity. "
            f"Returns the top-{top_k} matching chunks with their source paths and content."
        )

    @staticmethod
    def _parse_optional_int(
        raw: str | None,
        *,
        default: int,
        field_name: str,
        min_value: int = 1,
    ) -> int:
        if raw is None or not raw.strip():
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer") from exc
        if value < min_value:
            raise ValueError(f"{field_name} must be >= {min_value}")
        if field_name.endswith("TOP_K") and value > _MAX_TOP_K:
            raise ValueError(f"{field_name} must be <= {_MAX_TOP_K}")
        return value

    @staticmethod
    def _parse_tool_names(raw: str) -> list[str]:
        names = [name.strip().lower() for name in raw.split(",") if name.strip()]
        if not names:
            return []

        seen: set[str] = set()
        duplicates: set[str] = set()
        for name in names:
            if name in seen:
                duplicates.add(name)
            seen.add(name)
        if duplicates:
            dup_text = ", ".join(sorted(duplicates))
            raise ValueError(f"AGENTS_KNOWLEDGE__TOOLS contains duplicates: {dup_text}")

        for name in names:
            if len(name) > _MAX_TOOL_NAME_LEN:
                raise ValueError(f"AGENTS_KNOWLEDGE__TOOLS name too long: {name}")
            if not _TOOL_NAME_PATTERN.match(name):
                raise ValueError(f"Invalid tool name in AGENTS_KNOWLEDGE__TOOLS: {name}")
            if name in _RESERVED_TOOL_NAMES:
                raise ValueError(f"AGENTS_KNOWLEDGE__TOOLS conflicts with built-in tool: {name}")
        return names


@lru_cache
def get_agents_knowledge_settings() -> AgentsKnowledgeSettings:
    return AgentsKnowledgeSettings()


__all__ = [
    "AgentsKnowledgeSettings",
    "AgentsKnowledgeToolConfig",
    "KNOWLEDGE_COLLECTION_FIELD",
    "get_agents_knowledge_settings",
]
