from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache, lru_cache
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from langchain_core.runnables import RunnableConfig

from concierge.loggers import get_logger
from concierge.settings import get_microsoft_foundry_settings, get_observability_settings

logger = get_logger(__name__)


@dataclass
class _State:
    tracing_enabled: bool = False
    mlflow_enabled: bool = False


_state = _State()


def enable_tracing() -> None:
    _state.tracing_enabled = True


def disable_tracing() -> None:
    _state.tracing_enabled = False


def is_tracing_enabled() -> bool:
    return _state.tracing_enabled


def _is_http_tracking_uri(tracking_uri: str) -> bool:
    """Return True if the tracking URI targets a remote HTTP(S) MLflow server.

    Non-HTTP backends (``file:``, ``sqlite:``, ``databricks:``, ...) do not
    require a running server, so we skip the reachability probe for them.
    """
    scheme = urlparse(tracking_uri).scheme.lower()
    return scheme in {"http", "https"}


def _is_mlflow_server_reachable(tracking_uri: str, timeout: float) -> bool:
    """Probe ``<tracking_uri>/health`` with a short timeout.

    Returns ``True`` when the server responds (any HTTP status is treated as
    "reachable" — the MLflow process is alive even if /health is missing on
    older versions). Returns ``False`` on connection errors / timeouts so the
    caller can degrade gracefully instead of blocking on MLflow's internal
    retry loop.
    """
    probe_url = tracking_uri.rstrip("/") + "/health"
    try:
        with urllib_request.urlopen(probe_url, timeout=timeout):  # noqa: S310 - configured tracking URI
            return True
    except urllib_error.HTTPError:
        # Server responded with a non-2xx status. It is still reachable.
        return True
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "MLflow tracking server is not reachable at %s (timeout=%.1fs): %s",
            tracking_uri,
            timeout,
            exc,
        )
        return False


def _apply_mlflow_http_env_defaults(
    *,
    request_timeout: float,
    max_retries: int,
) -> None:
    """Apply fail-fast defaults for MLflow's REST client via env vars.

    Uses ``setdefault`` so any value the user already exported wins. MLflow
    reads these env vars on first use of its HTTP client. Both variables
    are parsed by MLflow as ``int``, so we coerce to ``int`` before writing
    even though the timeout setting is exposed as ``float`` for ergonomics.
    """
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", str(int(request_timeout)))
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", str(int(max_retries)))


@lru_cache(maxsize=1)
def _enable_mlflow_once() -> None:
    import mlflow

    observability_settings = get_observability_settings()
    tracking_uri = observability_settings.mlflow_tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(observability_settings.mlflow_experiment_name)
    mlflow.langchain.autolog()
    logger.info("MLflow autologging enabled (tracking_uri=%s)", tracking_uri)


def enable_mlflow() -> None:
    """Enable MLflow autologging with a fail-fast guard.

    If the configured tracking server is an HTTP endpoint that does not
    respond within ``mlflow_health_check_timeout_seconds``, MLflow stays
    disabled and a warning is logged instead of blocking the caller on
    MLflow's internal HTTP retry loop. Any unexpected exception during the
    actual MLflow setup is also caught so a flaky server cannot crash the
    application; the ``lru_cache`` is cleared so the next call retries.
    """
    observability_settings = get_observability_settings()
    tracking_uri = observability_settings.mlflow_tracking_uri

    _apply_mlflow_http_env_defaults(
        request_timeout=observability_settings.mlflow_http_request_timeout_seconds,
        max_retries=observability_settings.mlflow_http_request_max_retries,
    )

    if _is_http_tracking_uri(tracking_uri) and not _is_mlflow_server_reachable(
        tracking_uri,
        observability_settings.mlflow_health_check_timeout_seconds,
    ):
        logger.warning(
            "Skipping MLflow autologging because the tracking server at %s "
            "is not reachable. Start the MLflow server or unset "
            "CONCIERGE_MLFLOW_ENABLED to silence this warning.",
            tracking_uri,
        )
        _state.mlflow_enabled = False
        return

    try:
        _enable_mlflow_once()
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any MLflow error
        logger.warning(
            "Failed to enable MLflow autologging (tracking_uri=%s): %s. Continuing without MLflow.",
            tracking_uri,
            exc,
        )
        # Allow a future call (e.g. after the server comes back) to retry.
        _enable_mlflow_once.cache_clear()
        _state.mlflow_enabled = False
        return

    _state.mlflow_enabled = True


def is_mlflow_enabled() -> bool:
    return _state.mlflow_enabled


@cache
def get_tracer(service_name: str):
    from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer

    return AzureAIOpenTelemetryTracer(
        project_endpoint=get_microsoft_foundry_settings().azure_ai_project_endpoint,
        credential=DefaultAzureCredential(),
        name=service_name,
    )


def trace_config(
    service_name: str,
    extra: dict[str, Any] | None = None,
) -> RunnableConfig:
    config: dict[str, Any] = dict(extra or {})
    if is_tracing_enabled():
        callbacks = list(config.get("callbacks", []))
        callbacks.append(get_tracer(service_name))
        config["callbacks"] = callbacks
    return RunnableConfig(**config)


def bootstrap_from_env(service_name: str) -> None:
    _ = service_name
    observability_settings = get_observability_settings()
    if observability_settings.concierge_tracing_enabled:
        enable_tracing()
    else:
        disable_tracing()
    if observability_settings.concierge_mlflow_enabled:
        enable_mlflow()
