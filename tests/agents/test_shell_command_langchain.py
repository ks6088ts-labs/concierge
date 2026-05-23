from __future__ import annotations

from pathlib import Path

from concierge.agents.infrastructure.tools.shell_command import ShellCommandConfig
from concierge.agents.infrastructure.tools.shell_command_tool import build_shell_langchain_tool_builders


def test_langchain_shell_tool_builder_signature(tmp_path: Path) -> None:
    config = ShellCommandConfig(
        allowed_commands=("echo",),
        root_dir=tmp_path,
    )
    builders = build_shell_langchain_tool_builders(config, "shell_exec")
    shell_exec = builders[0]({})
    assert shell_exec.name == "shell_exec"


def test_langchain_shell_tool_returns_safe_error(tmp_path: Path) -> None:
    config = ShellCommandConfig(
        allowed_commands=("echo",),
        root_dir=tmp_path,
    )
    builders = build_shell_langchain_tool_builders(config, "shell_exec")
    shell_exec = builders[0]({})
    result = shell_exec.invoke({"command": "ls"})
    assert result.startswith("Error:")
