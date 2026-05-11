from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict

import mlflow
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from concierge.loggers import get_logger
from concierge.settings import get_observability_settings, get_todo_settings
from concierge.todo.domain.exceptions import DomainError, TaskNotFoundError, TaskValidationError
from concierge.todo.infrastructure.web.routes.tasks import router as tasks_router
from concierge.todo.interfaces.view_models.base import ErrorViewModel

logger = get_logger(__name__)


def create_app(*, tracer_provider: TracerProvider | None = None) -> FastAPI:
    settings = get_todo_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(tasks_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(TaskValidationError)
    async def handle_validation_error(_, exc: TaskValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400, content=asdict(ErrorViewModel(error="task_validation_error", detail=str(exc)))
        )

    @app.exception_handler(TaskNotFoundError)
    async def handle_not_found_error(_, exc: TaskNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=asdict(ErrorViewModel(error="task_not_found", detail=str(exc))))

    @app.exception_handler(DomainError)
    async def handle_domain_error(_, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content=asdict(ErrorViewModel(error="domain_error", detail=str(exc))))

    _configure_observability(app, tracer_provider=tracer_provider)
    return app


def _configure_observability(app: FastAPI, *, tracer_provider: TracerProvider | None) -> None:
    todo_settings = get_todo_settings()
    observability_settings = get_observability_settings()
    provider = tracer_provider or TracerProvider(resource=Resource.create({"service.name": todo_settings.app_name}))

    if observability_settings.application_insights_connection_string:
        exporter = AzureMonitorTraceExporter(
            connection_string=observability_settings.application_insights_connection_string,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    if todo_settings.enable_mlflow:
        with suppress(Exception):
            mlflow.set_tracking_uri(observability_settings.mlflow_tracking_uri)
            mlflow.set_experiment(observability_settings.mlflow_experiment_name)
            logger.info(
                "MLflow configured for todo app (tracking_uri=%s)",
                observability_settings.mlflow_tracking_uri,
            )
