from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


@dataclass(frozen=True, slots=True)
class Result(Generic[T, E]):
    value: T | None = None
    error: E | None = None

    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        return cls(value=value)

    @classmethod
    def err(cls, error: E) -> Result[T, E]:
        return cls(error=error)

    @property
    def is_ok(self) -> bool:
        return self.error is None

    @property
    def is_error(self) -> bool:
        return self.error is not None
