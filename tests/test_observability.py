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
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)
    call_counts = {
        "set_tracking_uri": 0,
        "set_experiment": 0,
        "autolog": 0,
        "openai_autolog": 0,
        "maf_tracing": 0,
    }

    fake_mlflow = types.SimpleNamespace()
    fake_mlflow.set_tracking_uri = lambda _uri: call_counts.__setitem__(
        "set_tracking_uri", call_counts["set_tracking_uri"] + 1
    )

    def _set_experiment(_name: str) -> SimpleNamespace:
        call_counts["set_experiment"] += 1
        return SimpleNamespace(experiment_id="42")

    fake_mlflow.set_experiment = _set_experiment
    fake_mlflow.langchain = types.SimpleNamespace(
        autolog=lambda: call_counts.__setitem__("autolog", call_counts["autolog"] + 1)
    )
    fake_mlflow.openai = types.SimpleNamespace(
        autolog=lambda: call_counts.__setitem__("openai_autolog", call_counts["openai_autolog"] + 1)
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(
            mlflow_tracking_uri="http://127.0.0.1:5000",
            mlflow_experiment_name="concierge",
            mlflow_health_check_timeout_seconds=3.0,
            mlflow_http_request_timeout_seconds=5.0,
            mlflow_http_request_max_retries=1,
        ),
    )
    monkeypatch.setattr(observability, "_is_mlflow_server_reachable", lambda _uri, _timeout: True)

    def _fake_maf_tracing(*, tracking_uri: str, experiment_id: str) -> None:
        _ = tracking_uri
        _ = experiment_id
        call_counts["maf_tracing"] += 1

    monkeypatch.setattr(
        observability,
        "_enable_microsoft_agent_framework_mlflow_tracing",
        _fake_maf_tracing,
    )

    observability.enable_mlflow()
    observability.enable_mlflow()

    assert call_counts == {
        "set_tracking_uri": 1,
        "set_experiment": 1,
        "autolog": 1,
        "openai_autolog": 1,
        "maf_tracing": 1,
    }
    import os

    assert os.environ["OTEL_EXPORTER_OTLP_HEADERS"] == "x-mlflow-experiment-id=42"
    assert observability.is_mlflow_enabled() is True


def test_enable_mlflow_skips_when_server_unreachable(monkeypatch, caplog) -> None:
    _reset_state()
    mlflow_calls: list[str] = []

    def _set_experiment(_name: str) -> SimpleNamespace:
        mlflow_calls.append("set_experiment")
        return SimpleNamespace(experiment_id="42")

    fake_mlflow = types.SimpleNamespace(
        set_tracking_uri=lambda _uri: mlflow_calls.append("set_tracking_uri"),
        set_experiment=_set_experiment,
        langchain=types.SimpleNamespace(autolog=lambda: mlflow_calls.append("autolog")),
        openai=types.SimpleNamespace(autolog=lambda: mlflow_calls.append("openai_autolog")),
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(
            mlflow_tracking_uri="http://127.0.0.1:5000",
            mlflow_experiment_name="concierge",
            mlflow_health_check_timeout_seconds=0.5,
            mlflow_http_request_timeout_seconds=5.0,
            mlflow_http_request_max_retries=1,
        ),
    )
    monkeypatch.setattr(observability, "_is_mlflow_server_reachable", lambda _uri, _timeout: False)

    with caplog.at_level("WARNING", logger=observability.logger.name):
        observability.enable_mlflow()

    assert observability.is_mlflow_enabled() is False
    assert mlflow_calls == []
    assert any("not reachable" in record.message for record in caplog.records)


def test_enable_mlflow_swallows_setup_exception(monkeypatch, caplog) -> None:
    _reset_state()

    def _raise(_uri: str) -> None:
        raise RuntimeError("boom")

    fake_mlflow = types.SimpleNamespace(
        set_tracking_uri=_raise,
        set_experiment=lambda _name: None,
        langchain=types.SimpleNamespace(autolog=lambda: None),
        openai=types.SimpleNamespace(autolog=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(
            mlflow_tracking_uri="http://127.0.0.1:5000",
            mlflow_experiment_name="concierge",
            mlflow_health_check_timeout_seconds=3.0,
            mlflow_http_request_timeout_seconds=5.0,
            mlflow_http_request_max_retries=1,
        ),
    )
    monkeypatch.setattr(observability, "_is_mlflow_server_reachable", lambda _uri, _timeout: True)

    with caplog.at_level("WARNING", logger=observability.logger.name):
        observability.enable_mlflow()

    assert observability.is_mlflow_enabled() is False
    assert any("Failed to enable MLflow" in record.message for record in caplog.records)
    # Cache must be cleared so a subsequent call retries instead of returning
    # the cached (failed) result.
    assert observability._enable_mlflow_once.cache_info().currsize == 0


def test_enable_mlflow_skips_health_check_for_non_http_uri(monkeypatch) -> None:
    _reset_state()
    mlflow_calls: list[str] = []

    def _set_experiment(_name: str) -> SimpleNamespace:
        mlflow_calls.append("set_experiment")
        return SimpleNamespace(experiment_id="42")

    fake_mlflow = types.SimpleNamespace(
        set_tracking_uri=lambda _uri: mlflow_calls.append("set_tracking_uri"),
        set_experiment=_set_experiment,
        langchain=types.SimpleNamespace(autolog=lambda: mlflow_calls.append("autolog")),
        openai=types.SimpleNamespace(autolog=lambda: mlflow_calls.append("openai_autolog")),
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(
            mlflow_tracking_uri="file:./mlruns",
            mlflow_experiment_name="concierge",
            mlflow_health_check_timeout_seconds=3.0,
            mlflow_http_request_timeout_seconds=5.0,
            mlflow_http_request_max_retries=1,
        ),
    )

    def _fail_if_called(_uri: str, _timeout: float) -> bool:
        raise AssertionError("health check should be skipped for non-HTTP URIs")

    monkeypatch.setattr(observability, "_is_mlflow_server_reachable", _fail_if_called)

    observability.enable_mlflow()

    assert observability.is_mlflow_enabled() is True
    assert mlflow_calls == ["set_tracking_uri", "set_experiment", "autolog", "openai_autolog"]


def test_enable_microsoft_agent_framework_mlflow_tracing_configures_otel(monkeypatch) -> None:
    """OTel exporter is wired to ``<tracking_uri>/v1/traces`` with the experiment header."""
    _reset_state()

    captured: dict[str, object] = {}

    class _FakeExporter:
        def __init__(self, *, endpoint: str, headers: dict[str, str]) -> None:
            captured["endpoint"] = endpoint
            captured["headers"] = headers

    def _fake_configure(*, enable_sensitive_data: bool, exporters: list[object]) -> None:
        captured["enable_sensitive_data"] = enable_sensitive_data
        captured["exporters"] = exporters

    af_obs = types.ModuleType("agent_framework.observability")
    setattr(af_obs, "configure_otel_providers", _fake_configure)
    af_pkg = types.ModuleType("agent_framework")
    setattr(af_pkg, "observability", af_obs)
    monkeypatch.setitem(sys.modules, "agent_framework", af_pkg)
    monkeypatch.setitem(sys.modules, "agent_framework.observability", af_obs)

    otel_trace_module = types.ModuleType("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    setattr(otel_trace_module, "OTLPSpanExporter", _FakeExporter)
    for module_name in (
        "opentelemetry",
        "opentelemetry.exporter",
        "opentelemetry.exporter.otlp",
        "opentelemetry.exporter.otlp.proto",
        "opentelemetry.exporter.otlp.proto.http",
    ):
        monkeypatch.setitem(sys.modules, module_name, types.ModuleType(module_name))
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        otel_trace_module,
    )

    observability._enable_microsoft_agent_framework_mlflow_tracing(
        tracking_uri="http://127.0.0.1:5000/",
        experiment_id="42",
    )

    assert captured["endpoint"] == "http://127.0.0.1:5000/v1/traces"
    assert captured["headers"] == {"x-mlflow-experiment-id": "42"}
    assert captured["enable_sensitive_data"] is True
    assert isinstance(captured["exporters"], list)
    assert len(captured["exporters"]) == 1
    assert isinstance(captured["exporters"][0], _FakeExporter)


def test_enable_microsoft_agent_framework_mlflow_tracing_skips_non_http(monkeypatch) -> None:
    """File-based tracking URIs cannot accept OTLP, so the exporter is not wired."""
    _reset_state()

    called: dict[str, bool] = {}

    def _fail_if_called(*, enable_sensitive_data: bool, exporters: list[object]) -> None:
        _ = enable_sensitive_data
        _ = exporters
        called["configure"] = True

    af_obs = types.ModuleType("agent_framework.observability")
    setattr(af_obs, "configure_otel_providers", _fail_if_called)
    monkeypatch.setitem(sys.modules, "agent_framework.observability", af_obs)

    observability._enable_microsoft_agent_framework_mlflow_tracing(
        tracking_uri="file:./mlruns",
        experiment_id="42",
    )

    assert called == {}


def test_enable_microsoft_agent_framework_mlflow_tracing_degrades_when_missing(monkeypatch, caplog) -> None:
    """A missing OTLP exporter package logs a warning and does not raise."""
    _reset_state()

    # Force the OTLP HTTP exporter import to fail by removing the parent module
    # so the nested import inside the helper raises ImportError.
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        None,
    )

    with caplog.at_level("WARNING", logger=observability.logger.name):
        observability._enable_microsoft_agent_framework_mlflow_tracing(
            tracking_uri="http://127.0.0.1:5000",
            experiment_id="42",
        )

    assert any("Microsoft Agent Framework" in record.message for record in caplog.records)


def test_apply_mlflow_http_env_defaults_respects_existing(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setenv("MLFLOW_HTTP_REQUEST_TIMEOUT", "42")
    monkeypatch.delenv("MLFLOW_HTTP_REQUEST_MAX_RETRIES", raising=False)

    observability._apply_mlflow_http_env_defaults(request_timeout=5.0, max_retries=1)

    import os

    # Pre-existing value preserved, missing one gets the default.
    assert os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] == "42"
    assert os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] == "1"


def test_append_mlflow_experiment_header_sets_when_missing(monkeypatch) -> None:
    _reset_state()
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)

    observability._append_mlflow_experiment_header("42")

    import os

    assert os.environ["OTEL_EXPORTER_OTLP_HEADERS"] == "x-mlflow-experiment-id=42"


def test_append_mlflow_experiment_header_appends_to_existing(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=Bearer abc")

    observability._append_mlflow_experiment_header("42")

    import os

    assert os.environ["OTEL_EXPORTER_OTLP_HEADERS"] == ("authorization=Bearer abc,x-mlflow-experiment-id=42")


def test_append_mlflow_experiment_header_does_not_duplicate_existing(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "x-mlflow-experiment-id=1,foo=bar")

    observability._append_mlflow_experiment_header("42")

    import os

    assert os.environ["OTEL_EXPORTER_OTLP_HEADERS"] == "x-mlflow-experiment-id=1,foo=bar"


def test_build_copilot_sdk_telemetry_config_returns_none_when_mlflow_disabled(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setattr(observability, "is_mlflow_enabled", lambda: False)

    assert observability.build_copilot_sdk_telemetry_config() is None


def test_build_copilot_sdk_telemetry_config_returns_none_for_non_http_tracking_uri(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setattr(observability, "is_mlflow_enabled", lambda: True)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(mlflow_tracking_uri="file:./mlruns"),
    )

    assert observability.build_copilot_sdk_telemetry_config() is None


def test_build_copilot_sdk_telemetry_config_returns_config_for_http_tracking_uri(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setattr(observability, "is_mlflow_enabled", lambda: True)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(mlflow_tracking_uri="http://127.0.0.1:5000"),
    )

    assert observability.build_copilot_sdk_telemetry_config() == {
        "otlp_endpoint": "http://127.0.0.1:5000",
        "source_name": "concierge.github-copilot-sdk",
        "capture_content": False,
    }


def test_build_copilot_sdk_telemetry_config_sets_bsp_schedule_delay_default(monkeypatch) -> None:
    """A short BSP delay is required so the CLI subprocess flushes spans before exiting."""
    _reset_state()
    monkeypatch.delenv("OTEL_BSP_SCHEDULE_DELAY", raising=False)
    monkeypatch.setattr(observability, "is_mlflow_enabled", lambda: True)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(mlflow_tracking_uri="http://127.0.0.1:5000"),
    )

    observability.build_copilot_sdk_telemetry_config()

    import os

    assert os.environ["OTEL_BSP_SCHEDULE_DELAY"] == "500"


def test_build_copilot_sdk_telemetry_config_keeps_existing_bsp_schedule_delay(monkeypatch) -> None:
    _reset_state()
    monkeypatch.setenv("OTEL_BSP_SCHEDULE_DELAY", "1234")
    monkeypatch.setattr(observability, "is_mlflow_enabled", lambda: True)
    monkeypatch.setattr(
        observability,
        "get_observability_settings",
        lambda: SimpleNamespace(mlflow_tracking_uri="http://127.0.0.1:5000"),
    )

    observability.build_copilot_sdk_telemetry_config()

    import os

    assert os.environ["OTEL_BSP_SCHEDULE_DELAY"] == "1234"


def test_build_copilot_sdk_telemetry_config_does_not_set_bsp_when_disabled(monkeypatch) -> None:
    """No env-var side effect when telemetry config returns None."""
    _reset_state()
    monkeypatch.delenv("OTEL_BSP_SCHEDULE_DELAY", raising=False)
    monkeypatch.setattr(observability, "is_mlflow_enabled", lambda: False)

    assert observability.build_copilot_sdk_telemetry_config() is None

    import os

    assert "OTEL_BSP_SCHEDULE_DELAY" not in os.environ


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
