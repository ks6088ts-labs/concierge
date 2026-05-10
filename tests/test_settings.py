from logging import DEBUG

from dotenv import load_dotenv

from concierge.loggers import get_logger
from concierge.settings import ObservabilitySettings, ProjectSettings

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
