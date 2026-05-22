from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.cli.app import app
from concierge.agents.infrastructure.github_copilot_echo_agent import GitHubCopilotEchoAgent
from concierge.agents.infrastructure.microsoft_agent_framework_agent import MicrosoftAgentFrameworkAgent
from concierge.agents.infrastructure.tools.image_generation import GeneratedImage, ImageGenerationResult

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
    for expected in AgentType:
        assert expected in agent_types


def test_cli_invoke_echo_with_payload_succeeds() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", AgentType.ECHO, "--payload", '{"message": "hello"}'],
    )
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "succeeded"
    assert response["result"] == {"echo": "hello", "reply": "hello"}
    assert response["error"] is None


def test_cli_invoke_echo_with_message_shortcut() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", AgentType.ECHO, "--message", "shortcut"],
    )
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "succeeded"
    assert response["result"] == {"echo": "shortcut", "reply": "shortcut"}


def test_cli_invoke_github_copilot_echo_with_message_shortcut() -> None:
    """The CLI runs the github-copilot-echo agent end-to-end, with the SDK session mocked.

    The Copilot SDK opens a real CLI subprocess on ``CopilotClient.__aenter__``,
    so the unit test patches ``_run_session`` to return a canned reply. The
    rest of the CLI ↔ agent ↔ registry chain still runs unmodified.
    """
    with patch.object(
        GitHubCopilotEchoAgent,
        "_run_session",
        new=AsyncMock(return_value="Hello Copilot"),
    ):
        result = runner.invoke(
            app,
            ["invoke", "--agent-type", AgentType.GITHUB_COPILOT_ECHO, "--message", "Hello Copilot"],
        )

    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "succeeded"
    assert response["result"] == {
        "echo": "Hello Copilot",
        "reply": "Hello Copilot",
        "model": "gpt-5-mini",
    }


def test_cli_invoke_microsoft_agent_framework_echo_with_message_shortcut() -> None:
    with patch.object(
        MicrosoftAgentFrameworkAgent,
        "_build_agent",
    ) as mock_build_agent:
        mock_framework_agent = AsyncMock()
        mock_framework_agent.run = AsyncMock(return_value=type("Response", (), {"text": "hello"})())
        mock_build_agent.return_value = mock_framework_agent
        result = runner.invoke(
            app,
            ["invoke", "--agent-type", AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO, "--message", "hello"],
        )

    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "succeeded"
    assert response["result"]["echo"] == "hello"
    assert response["result"]["reply"] == "hello"
    assert response["result"]["model"] == "gpt-5"


def test_cli_invoke_echo_missing_message_fails_with_exit_code_1() -> None:
    """Echo agent returns AgentResponse.status='failed' on empty payload.

    The CLI must propagate that as a non-zero exit code so shell scripts can
    detect failures without parsing JSON.
    """
    result = runner.invoke(app, ["invoke", "--agent-type", AgentType.ECHO])
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
        ["invoke", "--agent-type", AgentType.ECHO, "--payload", "not-json"],
    )
    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_cli_invoke_rejects_non_object_payload() -> None:
    result = runner.invoke(
        app,
        ["invoke", "--agent-type", AgentType.ECHO, "--payload", "[1, 2, 3]"],
    )
    assert result.exit_code == 1
    assert "must be a JSON object" in result.output


def test_cli_info_for_echo_agent() -> None:
    result = runner.invoke(app, ["info", "--agent-type", AgentType.ECHO])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == AgentType.ECHO
    assert info["class"] == "EchoAgent"
    assert info["module"].startswith("concierge.agents.infrastructure")


def test_cli_info_for_langgraph_echo_includes_settings() -> None:
    result = runner.invoke(app, ["info", "--agent-type", AgentType.LANGGRAPH_ECHO])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == AgentType.LANGGRAPH_ECHO
    assert info["class"] == "LangGraphAgent"
    assert "settings" in info
    assert "langgraph_model" in info["settings"]
    assert "langgraph_system_prompt" in info["settings"]


def test_cli_info_for_github_copilot_echo_includes_settings() -> None:
    result = runner.invoke(app, ["info", "--agent-type", AgentType.GITHUB_COPILOT_ECHO])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == AgentType.GITHUB_COPILOT_ECHO
    assert info["class"] == "GitHubCopilotEchoAgent"
    assert "settings" in info
    assert "github_copilot_model" in info["settings"]
    assert "github_copilot_system_prompt" in info["settings"]


def test_cli_info_for_microsoft_agent_framework_echo_includes_settings() -> None:
    result = runner.invoke(app, ["info", "--agent-type", AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO
    assert info["class"] == "MicrosoftAgentFrameworkAgent"
    assert "settings" in info
    assert "microsoft_agent_framework_model" in info["settings"]
    assert "microsoft_agent_framework_system_prompt" in info["settings"]


def test_cli_info_for_langgraph_image_gen_includes_settings() -> None:
    result = runner.invoke(app, ["info", "--agent-type", AgentType.LANGGRAPH_IMAGE_GEN])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == AgentType.LANGGRAPH_IMAGE_GEN
    assert info["class"] == "LangGraphAgent"
    assert "settings" in info
    assert "image_model" in info["settings"]
    assert "image_size" in info["settings"]
    assert "image_n" in info["settings"]
    assert "image_api_version" in info["settings"]


def test_cli_info_for_microsoft_agent_framework_image_gen_includes_settings() -> None:
    result = runner.invoke(app, ["info", "--agent-type", AgentType.MICROSOFT_AGENT_FRAMEWORK_IMAGE_GEN])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["agent_type"] == AgentType.MICROSOFT_AGENT_FRAMEWORK_IMAGE_GEN
    assert info["class"] == "MicrosoftAgentFrameworkAgent"
    assert "settings" in info
    assert "image_model" in info["settings"]
    assert "image_size" in info["settings"]
    assert "image_n" in info["settings"]
    assert "image_api_version" in info["settings"]


def test_cli_image_generate_success_human_readable_output() -> None:
    with patch(
        "concierge.agents.infrastructure.cli.app.generate_image",
        new=AsyncMock(
            return_value=ImageGenerationResult(
                images=[GeneratedImage(b64_json="abc", path="/tmp/generated.png", revised_prompt="revised prompt")],
                model="gpt-image-2",
                size="1024x1024",
            )
        ),
    ):
        result = runner.invoke(
            app,
            ["image", "generate", "--prompt", "A cat", "--output-dir", "/tmp/out"],
        )

    assert result.exit_code == 0, result.output
    assert "Generated 1 image" in result.output
    assert "/tmp/generated.png" in result.output


def test_cli_image_generate_prompt_required() -> None:
    result = runner.invoke(app, ["image", "generate"])
    assert result.exit_code != 0


def test_cli_image_generate_json_excludes_base64_by_default() -> None:
    with patch(
        "concierge.agents.infrastructure.cli.app.generate_image",
        new=AsyncMock(
            return_value=ImageGenerationResult(
                images=[GeneratedImage(b64_json="abc", path="/tmp/generated.png", revised_prompt=None)],
                model="gpt-image-2",
                size="1024x1024",
            )
        ),
    ):
        result = runner.invoke(
            app,
            ["image", "generate", "--prompt", "A cat", "--json"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["images"][0]["b64_json"] is None


def test_cli_image_generate_json_includes_base64_when_requested() -> None:
    with patch(
        "concierge.agents.infrastructure.cli.app.generate_image",
        new=AsyncMock(
            return_value=ImageGenerationResult(
                images=[GeneratedImage(b64_json="abc", path="/tmp/generated.png", revised_prompt=None)],
                model="gpt-image-2",
                size="1024x1024",
            )
        ),
    ):
        result = runner.invoke(
            app,
            ["image", "generate", "--prompt", "A cat", "--json", "--include-base64"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["images"][0]["b64_json"] == "abc"


def test_cli_image_generate_writes_file_in_output_dir(tmp_path) -> None:
    out_file = tmp_path / "generated.png"
    out_file.write_bytes(b"png-bytes")
    with patch(
        "concierge.agents.infrastructure.cli.app.generate_image",
        new=AsyncMock(
            return_value=ImageGenerationResult(
                images=[GeneratedImage(b64_json=None, path=str(out_file), revised_prompt=None)],
                model="gpt-image-2",
                size="1024x1024",
            )
        ),
    ):
        result = runner.invoke(
            app,
            ["image", "generate", "--prompt", "A cat", "--output-dir", str(tmp_path), "--json"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["images"][0]["path"] is not None
    assert tmp_path.joinpath("generated.png").exists()


def test_cli_info_unknown_agent_type_returns_error() -> None:
    result = runner.invoke(app, ["info", "--agent-type", "does-not-exist"])
    assert result.exit_code == 1
    assert "does-not-exist" in result.output
