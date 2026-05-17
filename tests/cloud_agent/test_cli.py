from __future__ import annotations

from typer.testing import CliRunner

from concierge.cloud_agent.infrastructure.cli.app import app

runner = CliRunner()


def test_cli_help_includes_global_observability_options() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "tracing" in result.output
    assert "mlflow" in result.output
    assert "verbose" in result.output
