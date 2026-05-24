"""SDK-independent knowledge retrieval core for agent tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from concierge.knowledge import get_search_knowledge_use_case
from concierge.knowledge.application.use_cases import CollectionName
from concierge.loggers import get_logger
from concierge.settings.agents_knowledge import KNOWLEDGE_COLLECTION_FIELD, AgentsKnowledgeToolConfig

logger = get_logger(__name__)
_MAX_K = 20
_ELLIPSIS = "…"


class KnowledgeSearchParams(BaseModel):
    query: str = Field(description="Natural language search query")
    k: int | None = Field(
        default=None,
        ge=1,
        le=_MAX_K,
        description="Number of chunks to return; None falls back to tool default top_k",
    )


@dataclass(frozen=True)
class KnowledgeChunkHit:
    source: str
    chunk_index: int
    score: float
    content: str


def search_knowledge_chunks(
    *,
    config: AgentsKnowledgeToolConfig,
    query: str,
    k: int | None,
    tool_name: str,
) -> str:
    started_at = perf_counter()
    resolved_k = k if k is not None else config.top_k
    try:
        use_case = get_search_knowledge_use_case(config.collection)
        results = use_case.execute(collection=CollectionName(config.collection), query=query, k=resolved_k)
        hits: list[KnowledgeChunkHit] = []
        truncated = False

        for result in results:
            metadata = result.metadata if isinstance(result.metadata, dict) else {}
            score = _normalize_score(metadata.get("score"), metadata.get("distance"))
            content, is_truncated = _truncate_content(result.content, max_chars=config.max_chars)
            truncated = truncated or is_truncated
            hits.append(
                KnowledgeChunkHit(
                    source=str(metadata.get("source", "")),
                    chunk_index=_parse_chunk_index(metadata.get("chunk_index")),
                    score=score,
                    content=content,
                )
            )

        payload: dict[str, Any] = {
            KNOWLEDGE_COLLECTION_FIELD: config.collection,
            "hits": [
                {
                    "source": hit.source,
                    "chunk_index": hit.chunk_index,
                    "score": hit.score,
                    "content": hit.content,
                }
                for hit in hits
            ],
            "truncated": truncated,
        }
        if not hits:
            payload["message"] = "No matching knowledge."

        _log_summary(
            tool_name=tool_name,
            collection=config.collection,
            k=resolved_k,
            hit_count=len(hits),
            started_at=started_at,
        )
        return _compact_json(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "operation=knowledge_search_failed tool_name=%s collection=%s k=%s",
            tool_name,
            config.collection,
            resolved_k,
        )
        payload = {
            "error": f"knowledge search failed: {type(exc).__name__}",
            KNOWLEDGE_COLLECTION_FIELD: config.collection,
        }
        return _compact_json(payload)


def _normalize_score(raw_score: object, raw_distance: object) -> float:
    if isinstance(raw_score, int | float):
        score = float(raw_score)
    elif isinstance(raw_distance, int | float):
        score = 1.0 / (1.0 + float(raw_distance))
    else:
        score = 1.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def _truncate_content(content: str, *, max_chars: int) -> tuple[str, bool]:
    if len(content) <= max_chars:
        return content, False
    return f"{content[:max_chars]}{_ELLIPSIS}", True


def _parse_chunk_index(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return -1
    return -1


def _log_summary(*, tool_name: str, collection: str, k: int, hit_count: int, started_at: float) -> None:
    latency_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "operation=knowledge_search tool_name=%s collection=%s k=%s hit_count=%s latency_ms=%s",
        tool_name,
        collection,
        k,
        hit_count,
        latency_ms,
    )


def _compact_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
