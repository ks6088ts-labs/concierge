from logging import DEBUG

import pytest
from dotenv import load_dotenv

from concierge.loggers import get_logger
from concierge.settings import (
    ObservabilitySettings,
    ProjectSettings,
    TodoRepositoryBackend,
    TodoSettings,
)

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

    settings = ObservabilitySettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.mlflow_tracking_uri == "http://127.0.0.1:5000"
    assert settings.mlflow_experiment_name == "microsoft-foundry-vanilla"


def test_observability_settings_reads_env(monkeypatch):
    """MLFLOW_TRACKING_URI / MLFLOW_EXPERIMENT_NAME should override defaults."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://example.com:1234")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "my-experiment")

    settings = ObservabilitySettings(_env_file=None)  # ty: ignore[unknown-argument]

    assert settings.mlflow_tracking_uri == "http://example.com:1234"
    assert settings.mlflow_experiment_name == "my-experiment"


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
