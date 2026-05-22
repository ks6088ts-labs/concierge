"""Settings shared by all built-in agents (LangGraph etc.)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentsSettings(BaseSettings):
    langgraph_model: str = "azure_ai:gpt-5"
    langgraph_system_prompt: str = (
        "You are a helpful assistant. "
        "You have access to tools such as `echo` (which simply echoes the user's text back) "
        "and `generate_image_tool` (which produces images via gpt-image-2). "
        "Pick the appropriate tool based on the user's request: "
        "call `echo` for plain echo / smoke-test requests, "
        "and call `generate_image_tool` with a concise English prompt when the user asks for an image. "
        "Return the tool result as your final answer in one sentence."
    )
    github_copilot_model: str = "gpt-5-mini"
    github_copilot_system_prompt: str = (
        "You are a helpful coding assistant that provides code suggestions and explanations to users."
    )
    microsoft_agent_framework_model: str = "gpt-5"
    microsoft_agent_framework_system_prompt: str = (
        "You are a helpful assistant. "
        "You have access to tools such as `echo` (which simply echoes the user's text back) "
        "and `generate_image_tool` (which produces images via gpt-image-2). "
        "Pick the appropriate tool based on the user's request: "
        "call `echo` for plain echo / smoke-test requests, "
        "and call `generate_image_tool` with a concise English prompt when the user asks for an image. "
        "Return the tool result as your final answer in one sentence."
    )
    image_model: str = "gpt-image-2"
    image_size: str = "1024x1024"
    image_n: int = 1
    image_api_version: str = "2025-04-01-preview"

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
