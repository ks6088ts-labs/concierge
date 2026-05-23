from __future__ import annotations

from typer.testing import CliRunner

from concierge.knowledge.infrastructure.cli.app import app

runner = CliRunner()


def test_cli_help_includes_ingest_and_observability_flags() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output
    assert "tracing" in result.output
    assert "mlflow" in result.output
    assert "verbose" in result.output
