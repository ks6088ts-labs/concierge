from logging import DEBUG

import pytest
from dotenv import load_dotenv

from concierge.loggers import get_logger
from concierge.settings import (
    AgentsSettings,
    ObservabilitySettings,
    ProjectSettings,
    TodoRepositoryBackend,
    TodoSettings,
)
from concierge.settings.chat import ChatSettings

logger = get_logger(__name__)


def test_project_settings(caplog):
    """
    Test that ProjectSettings loads values correctly from the .env.template file.
    """
    logger.info("[TEST] Running test_project_settings")
    with caplog.at_level(DEBUG):
        assert load_dotenv(
            dotenv_path=".env.template",
            verbose=True,
        ), "Failed to load environment variables from .env.template"
        settings = ProjectSettings()
        assert settings.project_name == "concierge", "Default project name should be 'concierge'"
        logger.debug(f"Settings initialized: {settings}")


def test_observability_settings_defaults(monkeypatch):
    """ObservabilitySettings should fall back to documented defaults when env vars are unset."""
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.delenv("MLFLOW_EXPERIMENT_NAME", raising=False)
    monkeypatch.delenv("CONCIERGE_TRACING_ENABLED", raising=False)
    monkeypatch.delenv("CONCIERGE_MLFLOW_ENABLED", raising=False)

    settings = ObservabilitySettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.mlflow_tracking_uri == "http://127.0.0.1:5000"
    assert settings.mlflow_experiment_name == "microsoft-foundry-vanilla"
    assert settings.concierge_tracing_enabled is False
    assert settings.concierge_mlflow_enabled is False
    assert settings.mlflow_health_check_timeout_seconds == 3.0
    assert settings.mlflow_http_request_timeout_seconds == 5.0
    assert settings.mlflow_http_request_max_retries == 1


def test_observability_settings_reads_env(monkeypatch):
    """MLFLOW_TRACKING_URI / MLFLOW_EXPERIMENT_NAME should override defaults."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://example.com:1234")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "my-experiment")
    monkeypatch.setenv("CONCIERGE_TRACING_ENABLED", "true")
    monkeypatch.setenv("CONCIERGE_MLFLOW_ENABLED", "1")

    settings = ObservabilitySettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.mlflow_tracking_uri == "http://example.com:1234"
    assert settings.mlflow_experiment_name == "my-experiment"
    assert settings.concierge_tracing_enabled is True
    assert settings.concierge_mlflow_enabled is True


def test_todo_settings_defaults(monkeypatch):
    """TodoSettings should default to the in-memory backend."""
    monkeypatch.delenv("TODO_REPOSITORY_BACKEND", raising=False)
    monkeypatch.delenv("TODO_TABLE_NAME", raising=False)

    settings = TodoSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.repository_backend is TodoRepositoryBackend.MEMORY
    assert settings.table_name == "todo_tasks"


def test_todo_settings_reads_env(monkeypatch):
    """TODO_REPOSITORY_BACKEND / TODO_TABLE_NAME should override defaults."""
    monkeypatch.setenv("TODO_REPOSITORY_BACKEND", "postgres")
    monkeypatch.setenv("TODO_TABLE_NAME", "custom_tasks")

    settings = TodoSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.repository_backend is TodoRepositoryBackend.POSTGRES
    assert settings.table_name == "custom_tasks"


def test_todo_settings_rejects_unknown_backend(monkeypatch):
    """Invalid backend strings must fail validation rather than silently passing through."""
    monkeypatch.setenv("TODO_REPOSITORY_BACKEND", "unknown-backend")

    with pytest.raises(ValueError, match="repository_backend"):
        TodoSettings(_env_file=None)  # ty: ignore[unknown-argument]


def test_agents_settings_defaults(monkeypatch):
    """AgentsSettings should load default values when no env vars are set."""
    monkeypatch.delenv("AGENTS_LANGGRAPH_MODEL", raising=False)
    monkeypatch.delenv("AGENTS_LANGGRAPH_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("AGENTS_GITHUB_COPILOT_SDK_MODEL", raising=False)
    monkeypatch.delenv("AGENTS_GITHUB_COPILOT_SDK_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("AGENTS_MICROSOFT_AGENT_FRAMEWORK_MODEL", raising=False)
    monkeypatch.delenv("AGENTS_MICROSOFT_AGENT_FRAMEWORK_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("AGENTS_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("AGENTS_IMAGE_SIZE", raising=False)
    monkeypatch.delenv("AGENTS_IMAGE_N", raising=False)
    monkeypatch.delenv("AGENTS_IMAGE_API_VERSION", raising=False)

    settings = AgentsSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.langgraph_model == "azure_ai:gpt-5"
    assert "echo" in settings.langgraph_system_prompt.lower()
    assert "generate_image_tool" in settings.langgraph_system_prompt
    assert settings.github_copilot_sdk_model == "gpt-5-mini"
    assert "echo" in settings.github_copilot_sdk_system_prompt.lower()
    assert "generate_image_tool" in settings.github_copilot_sdk_system_prompt
    assert settings.microsoft_agent_framework_model == "gpt-5"
    assert "echo" in settings.microsoft_agent_framework_system_prompt.lower()
    assert "generate_image_tool" in settings.microsoft_agent_framework_system_prompt
    assert settings.image_model == "gpt-image-2"
    assert settings.image_size == "1024x1024"
    assert settings.image_n == 1
    assert settings.image_api_version == "2025-04-01-preview"


def test_agents_settings_reads_env(monkeypatch):
    """AGENTS_LANGGRAPH_MODEL / AGENTS_LANGGRAPH_SYSTEM_PROMPT should override defaults."""
    monkeypatch.setenv("AGENTS_LANGGRAPH_MODEL", "azure_ai:gpt-4o-mini")
    monkeypatch.setenv("AGENTS_LANGGRAPH_SYSTEM_PROMPT", "custom prompt")
    monkeypatch.setenv("AGENTS_GITHUB_COPILOT_SDK_MODEL", "gpt-4.1")
    monkeypatch.setenv("AGENTS_GITHUB_COPILOT_SDK_SYSTEM_PROMPT", "custom copilot prompt")
    monkeypatch.setenv("AGENTS_MICROSOFT_AGENT_FRAMEWORK_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("AGENTS_MICROSOFT_AGENT_FRAMEWORK_SYSTEM_PROMPT", "custom maf prompt")
    monkeypatch.setenv("AGENTS_IMAGE_MODEL", "gpt-image-2-fast")
    monkeypatch.setenv("AGENTS_IMAGE_SIZE", "1536x1024")
    monkeypatch.setenv("AGENTS_IMAGE_N", "2")
    monkeypatch.setenv("AGENTS_IMAGE_API_VERSION", "2025-05-01-preview")

    settings = AgentsSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.langgraph_model == "azure_ai:gpt-4o-mini"
    assert settings.langgraph_system_prompt == "custom prompt"
    assert settings.github_copilot_sdk_model == "gpt-4.1"
    assert settings.github_copilot_sdk_system_prompt == "custom copilot prompt"
    assert settings.microsoft_agent_framework_model == "gpt-4.1-mini"
    assert settings.microsoft_agent_framework_system_prompt == "custom maf prompt"
    assert settings.image_model == "gpt-image-2-fast"
    assert settings.image_size == "1536x1024"
    assert settings.image_n == 2
    assert settings.image_api_version == "2025-05-01-preview"


def test_cloud_agent_settings_no_langgraph_fields(monkeypatch):
    """CloudAgentSettings must NOT have langgraph_model / langgraph_system_prompt (clean break)."""
    from concierge.settings.cloud_agent import CloudAgentSettings

    settings = CloudAgentSettings(_env_file=None)  # ty: ignore[unknown-argument]
    assert not hasattr(settings, "langgraph_model")
    assert not hasattr(settings, "langgraph_system_prompt")


def test_chat_settings_defaults(monkeypatch):
    """ChatSettings.bot_agent_type should default to 'foundry'."""
    monkeypatch.delenv("CHAT_RESPONDER_BACKEND", raising=False)
    monkeypatch.delenv("CHAT_BOT_AGENT_TYPE", raising=False)

    settings = ChatSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.bot_agent_type == "foundry"
    # ChatResponderBackend has been removed; no such attribute should exist.
    assert not hasattr(settings, "responder_backend")
