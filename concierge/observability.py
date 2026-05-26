from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache, lru_cache
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from copilot.client import TelemetryConfig
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


def _enable_microsoft_agent_framework_mlflow_tracing(
    tracking_uri: str,
    experiment_id: str,
) -> None:
    """Forward Microsoft Agent Framework OTel spans to the MLflow tracking server.

    Microsoft Agent Framework does not have a dedicated ``mlflow.*.autolog()``
    flavour. MLflow ingests its traces via OpenTelemetry instead: spans are
    pushed to the tracking server's ``/v1/traces`` endpoint with the target
    experiment id supplied through the ``x-mlflow-experiment-id`` header.
    See https://mlflow.org/docs/latest/genai/tracing/integrations/listing/microsoft-agent-framework/.

    The integration only works against an HTTP-based tracking server (the OTLP
    endpoint is exposed by ``mlflow server``), and the optional
    ``opentelemetry-exporter-otlp-proto-http`` package must be importable.
    Missing dependencies degrade gracefully: a warning is logged and the
    rest of MLflow autologging continues to work.
    """
    if not _is_http_tracking_uri(tracking_uri):
        logger.info(
            "Skipping Microsoft Agent Framework -> MLflow OTel exporter for non-HTTP "
            "tracking URI %s. OTLP ingestion requires an MLflow tracking server.",
            tracking_uri,
        )
        return

    try:
        from agent_framework.observability import (  # noqa: PLC0415
            configure_otel_providers,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
    except ImportError as exc:
        logger.warning(
            "Skipping Microsoft Agent Framework -> MLflow OTel exporter (%s). "
            "Install opentelemetry-exporter-otlp-proto-http and agent-framework-core to enable it.",
            exc,
        )
        return

    endpoint = tracking_uri.rstrip("/") + "/v1/traces"
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={"x-mlflow-experiment-id": experiment_id},
    )
    # enable_sensitive_data=True records LLM inputs and outputs alongside the
    # spans. The Microsoft docs explicitly require it for useful traces; only
    # enable it for development / non-production tracking servers.
    configure_otel_providers(enable_sensitive_data=True, exporters=[exporter])
    logger.info(
        "Microsoft Agent Framework OTel tracing forwarded to MLflow at %s (experiment_id=%s)",
        endpoint,
        experiment_id,
    )


def _append_mlflow_experiment_header(experiment_id: str) -> None:
    """Append ``x-mlflow-experiment-id`` to ``OTEL_EXPORTER_OTLP_HEADERS``."""
    if not experiment_id:
        return
    header = f"x-mlflow-experiment-id={experiment_id}"
    existing = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    if not existing:
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = header
        return
    if "x-mlflow-experiment-id=" in existing:
        return
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"{existing},{header}"


@lru_cache(maxsize=1)
def _enable_mlflow_once() -> None:
    import mlflow

    observability_settings = get_observability_settings()
    tracking_uri = observability_settings.mlflow_tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    experiment = mlflow.set_experiment(observability_settings.mlflow_experiment_name)
    if _is_http_tracking_uri(tracking_uri):
        _append_mlflow_experiment_header(getattr(experiment, "experiment_id", ""))
    mlflow.langchain.autolog()
    # mlflow.langchain.autolog() patches LangChain's BaseCallbackManager, so it
    # only traces calls that go through a Runnable / chain / chat model. Direct
    # Embeddings.embed_documents() calls (made e.g. by PGVectorStore during
    # ingestion) bypass CallbackManager entirely. Enabling the OpenAI flavour
    # patches the underlying openai SDK client, which is what
    # init_embeddings("azure_ai:...") ultimately calls, so embedding requests
    # are recorded as spans too.
    try:
        mlflow.openai.autolog()
    except Exception as exc:  # noqa: BLE001 - non-fatal; langchain traces still work
        logger.warning(
            "Skipping mlflow.openai.autolog() (%s). LangChain-only traces will still be recorded.",
            exc,
        )
    # Microsoft Agent Framework uses its own OpenTelemetry pipeline; route those
    # spans to the MLflow tracking server alongside the autolog flavours so a
    # single --mlflow flag covers every supported agent backend.
    try:
        _enable_microsoft_agent_framework_mlflow_tracing(
            tracking_uri=tracking_uri,
            experiment_id=getattr(experiment, "experiment_id", ""),
        )
    except Exception as exc:  # noqa: BLE001 - non-fatal; LangChain traces still work
        logger.warning(
            "Failed to wire Microsoft Agent Framework OTel exporter to MLflow (%s). "
            "Other MLflow integrations are unaffected.",
            exc,
        )
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


def build_copilot_sdk_telemetry_config() -> TelemetryConfig | None:
    """Return Copilot SDK telemetry config when MLflow and HTTP tracking are enabled."""
    if not is_mlflow_enabled():
        return None
    tracking_uri = get_observability_settings().mlflow_tracking_uri
    if not _is_http_tracking_uri(tracking_uri):
        return None
    return TelemetryConfig(
        otlp_endpoint=tracking_uri,
        source_name="concierge.github-copilot-sdk",
        capture_content=False,
    )


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
