"""Settings shared by all built-in agents (LangGraph etc.)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentsSettings(BaseSettings):
    langgraph_model: str = "azure_ai:gpt-5"
    langgraph_system_prompt: str = (
        "You are a minimal echo agent. "
        "When you receive any user input, call the `echo` tool with the user's text verbatim, "
        "then return the tool result as your final answer in one sentence."
    )
    github_copilot_model: str = "gpt-5"
    github_copilot_system_prompt: str = (
        "You are a minimal echo agent backed by the GitHub Copilot SDK. "
        "When you receive any user input, return the user's text verbatim "
        "as your final answer in one sentence."
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="AGENTS_",
        extra="ignore",
    )


@lru_cache
def get_agents_settings() -> AgentsSettings:
    return AgentsSettings()
