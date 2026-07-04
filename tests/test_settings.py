from logging import DEBUG

import pytest
from dotenv import load_dotenv

from concierge.loggers import get_logger
from concierge.settings import (
    AgentsKnowledgeSettings,
    AgentsSettings,
    KnowledgeEmbeddingProvider,
    KnowledgeSettings,
    KnowledgeVectorBackend,
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
    monkeypatch.delenv("AGENTS_FILE_ROOT_DIR", raising=False)
    monkeypatch.delenv("AGENTS_FILE_TOOLS_ENABLED", raising=False)
    monkeypatch.delenv("AGENTS_SHELL_TOOLS_ENABLED", raising=False)
    monkeypatch.delenv("AGENTS_SHELL_ALLOWED_COMMANDS", raising=False)
    monkeypatch.delenv("AGENTS_SHELL_ROOT_DIR", raising=False)
    monkeypatch.delenv("AGENTS_SHELL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("AGENTS_SHELL_MAX_OUTPUT_BYTES", raising=False)

    settings = AgentsSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.langgraph_model == "azure_ai:gpt-5"
    assert "echo" in settings.langgraph_system_prompt.lower()
    assert "generate_image_tool" in settings.langgraph_system_prompt
    assert "read_file" in settings.langgraph_system_prompt
    assert "shell_exec" in settings.langgraph_system_prompt
    assert settings.github_copilot_sdk_model == "gpt-5-mini"
    assert "echo" in settings.github_copilot_sdk_system_prompt.lower()
    assert "generate_image_tool" in settings.github_copilot_sdk_system_prompt
    assert "read_file" in settings.github_copilot_sdk_system_prompt
    assert "shell_exec" in settings.github_copilot_sdk_system_prompt
    assert settings.microsoft_agent_framework_model == "gpt-5"
    assert "echo" in settings.microsoft_agent_framework_system_prompt.lower()
    assert "generate_image_tool" in settings.microsoft_agent_framework_system_prompt
    assert "read_file" in settings.microsoft_agent_framework_system_prompt
    assert "shell_exec" in settings.microsoft_agent_framework_system_prompt
    assert settings.file_root_dir == ""
    assert settings.file_tools_enabled == "read_file,list_directory,file_search"
    assert settings.shell_tools_enabled == ""
    assert settings.shell_allowed_commands == ""
    assert settings.shell_root_dir == ""
    assert settings.shell_timeout_seconds == 30
    assert settings.shell_max_output_bytes == 65536
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
    monkeypatch.setenv("AGENTS_FILE_ROOT_DIR", "sandbox")
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "read_file,write_file")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "shell_exec")
    monkeypatch.setenv("AGENTS_SHELL_ALLOWED_COMMANDS", "terraform,echo")
    monkeypatch.setenv("AGENTS_SHELL_ROOT_DIR", "sandbox-shell")
    monkeypatch.setenv("AGENTS_SHELL_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("AGENTS_SHELL_MAX_OUTPUT_BYTES", "8192")

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
    assert settings.file_root_dir == "sandbox"
    assert settings.file_tools_enabled == "read_file,write_file"
    assert settings.shell_tools_enabled == "shell_exec"
    assert settings.shell_allowed_commands == "terraform,echo"
    assert settings.shell_root_dir == "sandbox-shell"
    assert settings.shell_timeout_seconds == 45
    assert settings.shell_max_output_bytes == 8192


def test_agents_knowledge_settings_defaults(monkeypatch):
    monkeypatch.delenv("AGENTS_KNOWLEDGE__TOOLS", raising=False)

    settings = AgentsKnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.configured_tools() == []


def test_agents_knowledge_settings_reads_env(monkeypatch):
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__TOP_K", "6")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__MAX_CHARS", "999")

    settings = AgentsKnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]
    configured = settings.configured_tools()

    assert len(configured) == 1
    assert configured[0].name == "search_docs"
    assert configured[0].collection == "docs"
    assert configured[0].top_k == 6
    assert configured[0].max_chars == 999


def test_agents_knowledge_settings_target_defaults_to_docker(monkeypatch):
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    monkeypatch.delenv("AGENTS_KNOWLEDGE__TARGET", raising=False)

    settings = AgentsKnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]
    configured = settings.configured_tools()

    assert configured[0].target == "docker"


def test_agents_knowledge_settings_target_reads_env(monkeypatch):
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TARGET", "azure")

    settings = AgentsKnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]
    configured = settings.configured_tools()

    assert configured[0].target == "azure"


def test_knowledge_settings_defaults(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("KNOWLEDGE_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("KNOWLEDGE_VECTOR_SIZE", raising=False)
    monkeypatch.delenv("KNOWLEDGE_VECTOR_BACKEND", raising=False)
    monkeypatch.delenv("KNOWLEDGE_DEFAULT_COLLECTION", raising=False)
    monkeypatch.delenv("KNOWLEDGE_CHUNK_SIZE", raising=False)
    monkeypatch.delenv("KNOWLEDGE_CHUNK_OVERLAP", raising=False)

    settings = KnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.embedding_provider is KnowledgeEmbeddingProvider.FOUNDRY
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.vector_size == 1536
    assert settings.vector_backend is KnowledgeVectorBackend.PGVECTOR
    assert settings.default_collection == "knowledge_default"
    assert settings.chunk_size == 1000
    assert settings.chunk_overlap == 200


def test_knowledge_settings_reads_env(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("KNOWLEDGE_EMBEDDING_MODEL", "test-model")
    monkeypatch.setenv("KNOWLEDGE_VECTOR_SIZE", "64")
    monkeypatch.setenv("KNOWLEDGE_VECTOR_BACKEND", "pgvector")
    monkeypatch.setenv("KNOWLEDGE_DEFAULT_COLLECTION", "runbooks")
    monkeypatch.setenv("KNOWLEDGE_CHUNK_SIZE", "256")
    monkeypatch.setenv("KNOWLEDGE_CHUNK_OVERLAP", "64")

    settings = KnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.embedding_provider is KnowledgeEmbeddingProvider.FAKE
    assert settings.embedding_model == "test-model"
    assert settings.vector_size == 64
    assert settings.vector_backend is KnowledgeVectorBackend.PGVECTOR
    assert settings.default_collection == "runbooks"
    assert settings.chunk_size == 256
    assert settings.chunk_overlap == 64


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


def test_chat_settings_accessibility_defaults(monkeypatch):
    """Accessibility mode ships a slow / simple-concept prompt and a slow TTS rate."""
    monkeypatch.delenv("CHAT_REALTIME_ACCESSIBLE_SYSTEM_PROMPT", raising=False)
    monkeypatch.delenv("CHAT_ACCESSIBLE_TTS_RATE", raising=False)

    settings = ChatSettings(_env_file=None)  # ty: ignore[unknown-argument]

    # The default prompt must differ from the standard realtime prompt so the
    # accessible session actually gets slower / simpler instructions.
    assert settings.realtime_accessible_system_prompt != settings.realtime_system_prompt
    assert settings.realtime_accessible_system_prompt.strip()
    # Slower than normal so synthesized speech is easier to follow.
    assert 0.0 < settings.accessible_tts_rate <= 1.0


def test_chat_settings_accessibility_reads_env(monkeypatch):
    """Accessibility settings honour their environment variables."""
    monkeypatch.setenv("CHAT_REALTIME_ACCESSIBLE_SYSTEM_PROMPT", "ゆっくり話してください")
    monkeypatch.setenv("CHAT_ACCESSIBLE_TTS_RATE", "0.6")

    settings = ChatSettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.realtime_accessible_system_prompt == "ゆっくり話してください"
    assert settings.accessible_tts_rate == pytest.approx(0.6)
