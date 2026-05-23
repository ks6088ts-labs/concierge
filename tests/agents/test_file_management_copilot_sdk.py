from __future__ import annotations

from pathlib import Path

import pytest
from copilot.tools import Tool, ToolInvocation

from concierge.agents.infrastructure.tools.file_management_tool import build_file_copilot_sdk_tool_builders


def test_copilot_file_tool_builder_returns_tools(tmp_path: Path) -> None:
    builders = build_file_copilot_sdk_tool_builders(str(tmp_path / "workspace"), "read_file,list_directory,file_search")
    tools = [builder({}) for builder in builders]
    assert all(isinstance(tool, Tool) for tool in tools)
    assert [tool.name for tool in tools] == ["read_file", "list_directory", "file_search"]


@pytest.mark.anyio
async def test_copilot_file_tool_handler_reads_file(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "hello.txt").write_text("hello", encoding="utf-8")
    builder = build_file_copilot_sdk_tool_builders(str(root), "read_file")[0]
    tool = builder({})

    result = await tool.handler(
        ToolInvocation(
            session_id="s1",
            tool_call_id="tc1",
            tool_name="read_file",
            arguments={"file_path": "hello.txt"},
        )
    )

    assert result.result_type == "success"
    assert result.text_result_for_llm == "hello"


@pytest.mark.anyio
async def test_copilot_file_tool_handler_returns_safe_error(tmp_path: Path) -> None:
    builder = build_file_copilot_sdk_tool_builders(str(tmp_path / "workspace"), "read_file")[0]
    tool = builder({})

    result = await tool.handler(
        ToolInvocation(
            session_id="s1",
            tool_call_id="tc1",
            tool_name="read_file",
            arguments={"file_path": "/etc/passwd"},
        )
    )

    assert result.result_type == "success"
    assert result.text_result_for_llm.startswith("Error:")
