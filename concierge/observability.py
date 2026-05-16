from __future__ import annotations

from dataclasses import dataclass
from functools import cache, lru_cache
from typing import Any

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
    _enable_mlflow_once()
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
