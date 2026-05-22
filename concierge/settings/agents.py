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
    github_copilot_model: str = "gpt-5-mini"
    github_copilot_system_prompt: str = (
        "You are a helpful coding assistant that provides code suggestions and explanations to users."
    )
    microsoft_agent_framework_model: str = "gpt-5"
    microsoft_agent_framework_system_prompt: str = (
        "You are a minimal echo agent. "
        "When you receive any user input, call the `echo` tool with the user's text verbatim, "
        "then return the tool result as your final answer in one sentence."
    )
    image_model: str = "gpt-image-2"
    image_size: str = "1024x1024"
    image_n: int = 1
    image_api_version: str = "2025-04-01-preview"
    langgraph_image_gen_system_prompt: str = (
        "You are an assistant that calls the `generate_image_tool` to produce images for the user. "
        "Always call the tool with a concise English prompt."
    )
    microsoft_agent_framework_image_gen_system_prompt: str = (
        "You are an assistant that calls the `generate_image_tool` to produce images for the user. "
        "Always call the tool with a concise English prompt."
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
