from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorViewModel:
    error: str
    detail: str


@dataclass(frozen=True, slots=True)
class MessageViewModel:
    detail: str
