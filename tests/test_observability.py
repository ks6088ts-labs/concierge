from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from concierge import observability
from concierge.settings import get_observability_settings


def _reset_state() -> None:
    observability.disable_tracing()
    observability._state.mlflow_enabled = False
    observability.get_tracer.cache_clear()
    observability._enable_mlflow_once.cache_clear()
    get_observability_settings.cache_clear()


def test_tracing_state_transitions() -> None:
    _reset_state()
    assert observability.is_tracing_enabled() is False
    observability.enable_tracing()
    assert observability.is_tracing_enabled() is True
    observability.disable_tracing()
    assert observability.is_tracing_enabled() is False


def test_trace_config_injects_tracer_when_enabled(monkeypatch) -> None:
    _reset_state()
    tracer = object()
    monkeypatch.setattr(observability, "get_tracer", lambda _service_name: tracer)
    observability.enable_tracing()

    config = observability.trace_config("svc")

    assert config["callbacks"] == [tracer]


def test_trace_config_keeps_existing_callbacks_when_tracing_disabled() -> None:
    _reset_state()
    existing = object()

    config = observability.trace_config("svc", extra={"callbacks": [existing]})

    assert config["callbacks"] == [existing]


def test_enable_mlflow_is_idempotent(monkeypatch) -> None:
    _reset_state()
    call_counts = {"set_tracking_uri": 0, "set_experiment": 0, "autolog": 0}

    fake_mlflow = types.SimpleNamespace()
    fake_mlflow.set_tracking_uri = lambda _uri: call_counts.__setitem__(
        "set_tracking_uri", call_counts["set_tracking_uri"] + 1
    )
    fake_mlflow.set_experiment = lambda _name: call_counts.__setitem__(
        "set_experiment", call_counts["set_experiment"] + 1
    )
    fake_mlflow.langchain = types.SimpleNamespace(
        autolog=lambda: call_counts.__setitem__("autolog", call_counts["autolog"] + 1)
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(mlflow_tracking_uri="http://127.0.0.1:5000", mlflow_experiment_name="concierge"),
    )

    observability.enable_mlflow()
    observability.enable_mlflow()

    assert call_counts == {"set_tracking_uri": 1, "set_experiment": 1, "autolog": 1}
    assert observability.is_mlflow_enabled() is True


def test_bootstrap_from_env_toggles_tracing(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setenv("CONCIERGE_TRACING_ENABLED", "true")
    monkeypatch.setenv("CONCIERGE_MLFLOW_ENABLED", "false")
    get_observability_settings.cache_clear()

    observability.bootstrap_from_env("svc")
    assert observability.is_tracing_enabled() is True

    monkeypatch.setenv("CONCIERGE_TRACING_ENABLED", "false")
    get_observability_settings.cache_clear()

    observability.bootstrap_from_env("svc")
    assert observability.is_tracing_enabled() is False


def test_get_tracer_is_cached_by_service_name(monkeypatch) -> None:
    _reset_state()
    calls: list[str] = []

    class FakeTracer:
        def __init__(self, *, project_endpoint: str, credential: object, name: str) -> None:
            _ = project_endpoint
            _ = credential
            calls.append(name)

    tracer_module = types.ModuleType("langchain_azure_ai.callbacks.tracers")
    setattr(tracer_module, "AzureAIOpenTelemetryTracer", FakeTracer)
    monkeypatch.setitem(sys.modules, "langchain_azure_ai", types.ModuleType("langchain_azure_ai"))
    monkeypatch.setitem(sys.modules, "langchain_azure_ai.callbacks", types.ModuleType("callbacks"))
    monkeypatch.setitem(sys.modules, "langchain_azure_ai.callbacks.tracers", tracer_module)
    monkeypatch.setattr(
        observability,
        "get_microsoft_foundry_settings",
        lambda: SimpleNamespace(azure_ai_project_endpoint="https://example"),
    )
    monkeypatch.setattr(observability, "DefaultAzureCredential", lambda: object())

    first = observability.get_tracer("svc-a")
    second = observability.get_tracer("svc-a")
    third = observability.get_tracer("svc-b")

    assert first is second
    assert first is not third
    assert calls == ["svc-a", "svc-b"]
