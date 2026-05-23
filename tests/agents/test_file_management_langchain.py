from __future__ import annotations

from pathlib import Path
from typing import Any

from concierge.agents.infrastructure.tools.file_management_tool import (
    READ_ONLY_FILE_TOOLS,
    build_file_langchain_tool_builders,
)


def test_build_file_langchain_tool_builders_default_tools(tmp_path: Path) -> None:
    builders = build_file_langchain_tool_builders(
        str(tmp_path / "workspace"),
        ",".join(READ_ONLY_FILE_TOOLS),
    )
    assert len(builders) == 3
    built = [builder({}) for builder in builders]
    assert [tool.name for tool in built] == list(READ_ONLY_FILE_TOOLS)


def test_langchain_file_tool_builder_signature(tmp_path: Path) -> None:
    builders = build_file_langchain_tool_builders(str(tmp_path / "workspace"), "read_file")
    side_outputs: dict[str, Any] = {}
    tool = builders[0](side_outputs)
    assert tool.name == "read_file"
