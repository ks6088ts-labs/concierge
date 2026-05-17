"""Shared pytest fixtures and helpers for the test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable tracing / MLflow during tests regardless of the developer's ``.env``.

    Several ``create_app()`` factories call ``load_dotenv()`` followed by
    ``bootstrap_from_env(...)`` at import / fixture-setup time. If the local
    ``.env`` has ``CONCIERGE_MLFLOW_ENABLED=true`` (or tracing), MLflow tries
    to connect to ``MLFLOW_TRACKING_URI`` (e.g. ``http://localhost:5000``) and
    the test setup blocks on retries when the server is not running.

    ``load_dotenv()`` uses ``override=False`` by default, so values already in
    ``os.environ`` win. Setting these env vars here therefore neutralises the
    ``.env`` for the duration of the test. We also reset the module-level
    observability singleton and the cached settings so prior tests cannot leak
    an enabled flag forward.
    """
    monkeypatch.setenv("CONCIERGE_TRACING_ENABLED", "false")
    monkeypatch.setenv("CONCIERGE_MLFLOW_ENABLED", "false")

    from concierge import observability  # noqa: PLC0415
    from concierge.settings import get_observability_settings  # noqa: PLC0415

    get_observability_settings.cache_clear()
    observability.disable_tracing()
    observability._state.mlflow_enabled = False
    observability.get_tracer.cache_clear()
    observability._enable_mlflow_once.cache_clear()


def skip_if_docker_unavailable() -> None:
    """Skip the current test if a usable Docker daemon is not reachable.

    Integration tests that rely on ``testcontainers`` require a running
    Docker daemon. In environments without Docker (for example, local
    development on a machine where Docker is not installed or not running),
    we skip these tests instead of erroring out at fixture setup.
    """
    try:
        import docker  # noqa: PLC0415

        docker.from_env().ping()
    except Exception as exc:  # docker.errors.DockerException and friends
        pytest.skip(f"Docker is not available: {exc}")
