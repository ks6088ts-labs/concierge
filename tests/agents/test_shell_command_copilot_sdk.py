from __future__ import annotations

from pathlib import Path

import pytest
from copilot.tools import Tool, ToolInvocation

from concierge.agents.infrastructure.tools.shell_command import ShellCommandConfig
from concierge.agents.infrastructure.tools.shell_command_tool import build_shell_copilot_sdk_tool_builders


def test_copilot_shell_tool_builder_returns_tool(tmp_path: Path) -> None:
    config = ShellCommandConfig(
        allowed_commands=("echo",),
        root_dir=tmp_path,
    )
    builders = build_shell_copilot_sdk_tool_builders(config, "shell_exec")
    tools = [builder({}) for builder in builders]
    assert len(tools) == 1
    assert isinstance(tools[0], Tool)
    assert tools[0].name == "shell_exec"


@pytest.mark.anyio
async def test_copilot_shell_tool_returns_safe_error(tmp_path: Path) -> None:
    config = ShellCommandConfig(
        allowed_commands=("echo",),
        root_dir=tmp_path,
    )
    builder = build_shell_copilot_sdk_tool_builders(config, "shell_exec")[0]
    tool = builder({})

    result = await tool.handler(
        ToolInvocation(
            session_id="s1",
            tool_call_id="tc1",
            tool_name="shell_exec",
            arguments={"command": "ls"},
        )
    )

    assert result.result_type == "success"
    assert result.text_result_for_llm.startswith("Error:")
