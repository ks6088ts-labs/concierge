from __future__ import annotations

from pathlib import Path


def test_maf_file_tool_builder_matches_core_behavior(tmp_path: Path) -> None:
    from concierge.agents.infrastructure.tools.file_management_tool import build_file_maf_tool_builders

    root = tmp_path / "workspace"
    root.mkdir()
    (root / "hello.txt").write_text("hello", encoding="utf-8")

    builders = build_file_maf_tool_builders(str(root), "read_file,list_directory,file_search")
    read_file = builders[0]({})
    list_directory = builders[1]({})
    file_search = builders[2]({})

    assert read_file("hello.txt") == "hello"
    assert "hello.txt" in list_directory(".")
    assert "hello.txt" in file_search("*.txt", ".")


def test_maf_file_tool_returns_safe_error(tmp_path: Path) -> None:
    from concierge.agents.infrastructure.tools.file_management_tool import build_file_maf_tool_builders

    builders = build_file_maf_tool_builders(str(tmp_path / "workspace"), "read_file")
    read_file = builders[0]({})
    result = read_file("/etc/passwd")
    assert result.startswith("Error:")
