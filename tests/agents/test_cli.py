from __future__ import annotations

import json

from typer.testing import CliRunner

from concierge.agents.infrastructure.cli.app import app

runner = CliRunner()


def test_cli_help_includes_global_observability_options() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "tracing" in result.output
    assert "mlflow" in result.output
    assert "verbose" in result.output


def test_cli_list_returns_registered_agent_types() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    agent_types = json.loads(result.output)
    assert "echo" in agent_types
    assert "langgraph-echo" in agent_types
    assert "github-copilot-echo" in agent_types


def test_cli_invoke_echo_with_payload_succeeds() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", "echo", "--payload", '{"message": "hello"}'],
    )
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "succeeded"
    assert response["result"] == {"echo": "hello", "reply": "hello"}
    assert response["error"] is None


def test_cli_invoke_echo_with_message_shortcut() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", "echo", "--message", "shortcut"],
    )
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "succeeded"
    assert response["result"] == {"echo": "shortcut", "reply": "shortcut"}


def test_cli_invoke_github_copilot_echo_with_message_shortcut() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", "github-copilot-echo", "--message", "Hello Copilot"],
    )
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "succeeded"
    assert response["result"] == {
        "echo": "Hello Copilot",
        "reply": "Hello Copilot",
        "client": {"initialized": True, "model": "gpt-5"},
    }


def test_cli_invoke_echo_missing_message_fails_with_exit_code_1() -> None:
    """Echo agent returns AgentResponse.status='failed' on empty payload.

    The CLI must propagate that as a non-zero exit code so shell scripts can
    detect failures without parsing JSON.
    """
    result = runner.invoke(app, ["invoke", "--agent-type", "echo"])
    assert result.exit_code == 1, result.output
    response = json.loads(result.output)
    assert response["status"] == "failed"
    assert response["error"] is not None


def test_cli_invoke_unknown_agent_type_returns_error() -> None:
    result = runner.invoke(app, ["invoke", "--agent-type", "does-not-exist"])
    assert result.exit_code == 1
    assert "does-not-exist" in result.output


def test_cli_invoke_rejects_invalid_payload_json() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", "echo", "--payload", "not-json"],
    )
    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_cli_invoke_rejects_non_object_payload() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", "echo", "--payload", "[1, 2, 3]"],
    )
    assert result.exit_code == 1
    assert "must be a JSON object" in result.output


def test_cli_info_for_echo_agent() -> None:
    result = runner.invoke(app, ["info", "--agent-type", "echo"])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == "echo"
    assert info["class"] == "EchoAgent"
    assert info["module"].startswith("concierge.agents.infrastructure")


def test_cli_info_for_langgraph_echo_includes_settings() -> None:
    result = runner.invoke(app, ["info", "--agent-type", "langgraph-echo"])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == "langgraph-echo"
    assert info["class"] == "LangGraphEchoAgent"
    assert "settings" in info
    assert "langgraph_model" in info["settings"]
    assert "langgraph_system_prompt" in info["settings"]


def test_cli_info_for_github_copilot_echo_includes_settings() -> None:
    result = runner.invoke(app, ["info", "--agent-type", "github-copilot-echo"])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == "github-copilot-echo"
    assert info["class"] == "GitHubCopilotEchoAgent"
    assert "settings" in info
    assert "github_copilot_model" in info["settings"]
    assert "github_copilot_system_prompt" in info["settings"]


def test_cli_info_unknown_agent_type_returns_error() -> None:
    result = runner.invoke(app, ["info", "--agent-type", "does-not-exist"])
    assert result.exit_code == 1
    assert "does-not-exist" in result.output
