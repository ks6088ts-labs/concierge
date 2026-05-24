from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from concierge.knowledge.domain.exceptions import CollectionValidationError

_COLLECTION_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class CollectionName:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise CollectionValidationError("collection name must not be empty")
        if not _COLLECTION_PATTERN.fullmatch(self.value):
            raise CollectionValidationError("collection name must match ^[A-Za-z0-9_]+$")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ContentHash:
    value: str

    @classmethod
    def from_text(cls, text: str) -> ContentHash:
        return cls(hashlib.sha256(text.encode("utf-8")).hexdigest())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ChunkId:
    value: str

    @classmethod
    def from_parts(
        cls,
        *,
        collection: CollectionName,
        source: str,
        chunk_index: int,
        content_hash: ContentHash,
    ) -> ChunkId:
        value = f"{collection}:{source}:{chunk_index}:{content_hash.value[:12]}"
        return cls(value)

    def __str__(self) -> str:
        return self.value
