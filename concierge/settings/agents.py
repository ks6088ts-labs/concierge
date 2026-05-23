"""Settings shared by all built-in agents (LangGraph etc.)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentsSettings(BaseSettings):
    langgraph_model: str = "azure_ai:gpt-5"
    langgraph_system_prompt: str = (
        "You are a helpful assistant. "
        "You have access to tools such as `echo` (which simply echoes the user's text back) "
        "and `generate_image_tool` (which produces images via gpt-image-2), plus sandboxed file tools "
        "such as `read_file`, `list_directory`, and `file_search` (and optional write tools when enabled), "
        "and optional shell tool `shell_exec` for allowlisted CLI commands. "
        "Pick the appropriate tool based on the user's request: "
        "call `echo` for plain echo / smoke-test requests, "
        "call `generate_image_tool` with a concise English prompt when the user asks for an image, "
        "use file tools for workspace file operations while staying within the sandbox root, "
        "and use `shell_exec` only when command execution is required. "
        "Return the tool result as your final answer in one sentence."
    )
    github_copilot_sdk_model: str = "gpt-5-mini"
    github_copilot_sdk_system_prompt: str = (
        "You are a helpful assistant. "
        "You have access to tools such as `echo` (which simply echoes the user's text back) "
        "and `generate_image_tool` (which produces images via gpt-image-2), plus sandboxed file tools "
        "such as `read_file`, `list_directory`, and `file_search` (and optional write tools when enabled), "
        "and optional shell tool `shell_exec` for allowlisted CLI commands. "
        "Pick the appropriate tool based on the user's request: "
        "call `echo` for plain echo / smoke-test requests, "
        "call `generate_image_tool` with a concise English prompt when the user asks for an image, "
        "use file tools for workspace file operations while staying within the sandbox root, "
        "and use `shell_exec` only when command execution is required. "
        "Return the tool result as your final answer in one sentence."
    )
    microsoft_agent_framework_model: str = "gpt-5"
    microsoft_agent_framework_system_prompt: str = (
        "You are a helpful assistant. "
        "You have access to tools such as `echo` (which simply echoes the user's text back) "
        "and `generate_image_tool` (which produces images via gpt-image-2), plus sandboxed file tools "
        "such as `read_file`, `list_directory`, and `file_search` (and optional write tools when enabled), "
        "and optional shell tool `shell_exec` for allowlisted CLI commands. "
        "Pick the appropriate tool based on the user's request: "
        "call `echo` for plain echo / smoke-test requests, "
        "call `generate_image_tool` with a concise English prompt when the user asks for an image, "
        "use file tools for workspace file operations while staying within the sandbox root, "
        "and use `shell_exec` only when command execution is required. "
        "Return the tool result as your final answer in one sentence."
    )
    file_root_dir: str = ""
    file_tools_enabled: str = "read_file,list_directory,file_search"
    shell_tools_enabled: str = ""
    shell_allowed_commands: str = ""
    shell_root_dir: str = ""
    shell_timeout_seconds: int = 30
    shell_max_output_bytes: int = 65536
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
