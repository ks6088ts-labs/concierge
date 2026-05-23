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


def test_langchain_file_tool_builder_matches_core_behavior(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "hello.txt").write_text("hello", encoding="utf-8")

    builders = build_file_langchain_tool_builders(str(root), "read_file,list_directory,file_search")
    read_file = builders[0]({})
    list_directory = builders[1]({})
    file_search = builders[2]({})

    assert read_file.invoke({"file_path": "hello.txt"}) == "hello"
    assert "hello.txt" in list_directory.invoke({"dir_path": "."})
    assert "hello.txt" in file_search.invoke({"pattern": "*.txt", "dir_path": "."})


def test_langchain_file_tool_returns_safe_error(tmp_path: Path) -> None:
    builders = build_file_langchain_tool_builders(str(tmp_path / "workspace"), "read_file")
    read_file = builders[0]({})
    result = read_file.invoke({"file_path": "/etc/passwd"})
    assert result.startswith("Error:")
