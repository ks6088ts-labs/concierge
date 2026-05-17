from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    mlflow_tracking_uri: str = "http://127.0.0.1:5000"
    mlflow_experiment_name: str = "microsoft-foundry-vanilla"
    concierge_tracing_enabled: bool = False
    concierge_mlflow_enabled: bool = False
    # Seconds to wait for the MLflow tracking server to respond during the
    # pre-flight reachability check. If the server is not reachable within
    # this budget, MLflow autologging is skipped (with a warning) instead of
    # blocking application startup on internal MLflow HTTP retries.
    mlflow_health_check_timeout_seconds: float = 3.0
    # Per-HTTP-request timeout (seconds) applied to MLflow's own REST client
    # via the MLFLOW_HTTP_REQUEST_TIMEOUT env var. Acts as a safety net for
    # any MLflow call that runs after initial bootstrap.
    mlflow_http_request_timeout_seconds: float = 5.0
    # Maximum number of retries MLflow performs for transient HTTP failures.
    # Lowered from the upstream default (which is intentionally aggressive)
    # so that a downed tracking server fails fast.
    mlflow_http_request_max_retries: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_observability_settings() -> ObservabilitySettings:
    return ObservabilitySettings()
