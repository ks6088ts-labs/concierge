"""File-management tool builders for LangChain, MAF, and Copilot SDK."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, Field

from concierge.agents.infrastructure.tools.exceptions import FileToolError
from concierge.agents.infrastructure.tools.file_management import FILE_TOOL_NAMES, FileManagementCore

READ_ONLY_FILE_TOOLS: tuple[str, ...] = ("read_file", "list_directory", "file_search")
_WRITE_FILE_TOOLS: set[str] = {"write_file", "copy_file", "move_file", "delete_file"}


class _ReadFileParams(BaseModel):
    file_path: str = Field(description="Relative path to the file")


class _ListDirectoryParams(BaseModel):
    dir_path: str = Field(default=".", description="Relative path to directory")


class _FileSearchParams(BaseModel):
    pattern: str = Field(description="Glob pattern to search")
    dir_path: str = Field(default=".", description="Relative path to directory")


class _WriteFileParams(BaseModel):
    file_path: str = Field(description="Relative destination file path")
    text: str = Field(description="Text content to write")


class _CopyFileParams(BaseModel):
    source_path: str = Field(description="Relative source file path")
    destination_path: str = Field(description="Relative destination file path")


class _MoveFileParams(BaseModel):
    source_path: str = Field(description="Relative source file path")
    destination_path: str = Field(description="Relative destination file path")


class _DeleteFileParams(BaseModel):
    file_path: str = Field(description="Relative file path to delete")


def parse_enabled_file_tools(value: str | Sequence[str]) -> list[str]:
    if isinstance(value, str):
        enabled = [name.strip() for name in value.split(",") if name.strip()]
    else:
        enabled = [str(name).strip() for name in value if str(name).strip()]

    unknown = sorted({name for name in enabled if name not in FILE_TOOL_NAMES})
    if unknown:
        raise ValueError(f"Unknown file tool(s): {', '.join(unknown)}")
    return enabled


def _tool_error_to_response(exc: Exception) -> str:
    return f"Error: {exc}"


def _build_langchain_builder(tool_name: str, root_dir: str) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from langchain_community.agent_toolkits.file_management.toolkit import FileManagementToolkit

        toolkit = FileManagementToolkit(root_dir=root_dir, selected_tools=[tool_name])
        return toolkit.get_tools()[0]

    return _build


def build_file_langchain_tool_builders(
    root_dir: str,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    resolved_root_dir = str(FileManagementCore.from_root_dir(root_dir).root_dir)
    selected = parse_enabled_file_tools(enabled)
    return [_build_langchain_builder(name, resolved_root_dir) for name in selected]


def _build_maf_builder(tool_name: str, core: FileManagementCore) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from agent_framework import tool

        if tool_name == "read_file":

            @tool
            def read_file(file_path: str) -> str:
                """Read a UTF-8 text file under sandbox root."""
                try:
                    return core.read_file(file_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return read_file

        if tool_name == "list_directory":

            @tool
            def list_directory(dir_path: str = ".") -> str:
                """List files under a directory in sandbox root."""
                try:
                    return core.list_directory(dir_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return list_directory

        if tool_name == "file_search":

            @tool
            def file_search(pattern: str, dir_path: str = ".") -> str:
                """Search files by glob pattern in sandbox root."""
                try:
                    return core.file_search(pattern, dir_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return file_search

        if tool_name == "write_file":

            @tool
            def write_file(file_path: str, text: str) -> str:
                """Write UTF-8 text content to a file in sandbox root."""
                try:
                    return core.write_file(file_path, text)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return write_file

        if tool_name == "copy_file":

            @tool
            def copy_file(source_path: str, destination_path: str) -> str:
                """Copy a file within sandbox root."""
                try:
                    return core.copy_file(source_path, destination_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return copy_file

        if tool_name == "move_file":

            @tool
            def move_file(source_path: str, destination_path: str) -> str:
                """Move a file within sandbox root."""
                try:
                    return core.move_file(source_path, destination_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return move_file

        if tool_name == "delete_file":

            @tool
            def delete_file(file_path: str) -> str:
                """Delete a file within sandbox root."""
                try:
                    return core.delete_file(file_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return delete_file

        raise ValueError(f"Unsupported file tool: {tool_name}")

    return _build


def build_file_maf_tool_builders(root_dir: str, enabled: str | Sequence[str]) -> list[Callable[[dict[str, Any]], Any]]:
    core = FileManagementCore.from_root_dir(root_dir)
    selected = parse_enabled_file_tools(enabled)
    return [_build_maf_builder(name, core) for name in selected]


def _build_copilot_builder(tool_name: str, core: FileManagementCore) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from copilot import define_tool

        if tool_name == "read_file":

            @define_tool(name="read_file", description="Read a UTF-8 text file in sandbox root.", skip_permission=True)
            def read_file(params: _ReadFileParams) -> str:
                try:
                    return core.read_file(params.file_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return read_file

        if tool_name == "list_directory":

            @define_tool(name="list_directory", description="List files in sandbox directory.", skip_permission=True)
            def list_directory(params: _ListDirectoryParams) -> str:
                try:
                    return core.list_directory(params.dir_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return list_directory

        if tool_name == "file_search":

            @define_tool(
                name="file_search",
                description="Search files by glob pattern in sandbox root.",
                skip_permission=True,
            )
            def file_search(params: _FileSearchParams) -> str:
                try:
                    return core.file_search(params.pattern, params.dir_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return file_search

        if tool_name == "write_file":

            @define_tool(
                name="write_file",
                description="Write UTF-8 text to file in sandbox root.",
                skip_permission=True,
            )
            def write_file(params: _WriteFileParams) -> str:
                try:
                    return core.write_file(params.file_path, params.text)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return write_file

        if tool_name == "copy_file":

            @define_tool(name="copy_file", description="Copy a file inside sandbox root.", skip_permission=True)
            def copy_file(params: _CopyFileParams) -> str:
                try:
                    return core.copy_file(params.source_path, params.destination_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return copy_file

        if tool_name == "move_file":

            @define_tool(name="move_file", description="Move/rename a file inside sandbox root.", skip_permission=True)
            def move_file(params: _MoveFileParams) -> str:
                try:
                    return core.move_file(params.source_path, params.destination_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return move_file

        if tool_name == "delete_file":

            @define_tool(name="delete_file", description="Delete a file inside sandbox root.", skip_permission=True)
            def delete_file(params: _DeleteFileParams) -> str:
                try:
                    return core.delete_file(params.file_path)
                except (FileToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return delete_file

        raise ValueError(f"Unsupported file tool: {tool_name}")

    return _build


def build_file_copilot_sdk_tool_builders(
    root_dir: str,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    core = FileManagementCore.from_root_dir(root_dir)
    selected = parse_enabled_file_tools(enabled)
    return [_build_copilot_builder(name, core) for name in selected]


def split_file_tools_by_access(enabled: str | Sequence[str]) -> tuple[list[str], list[str]]:
    selected = parse_enabled_file_tools(enabled)
    read_only = [name for name in selected if name not in _WRITE_FILE_TOOLS]
    writable = [name for name in selected if name in _WRITE_FILE_TOOLS]
    return read_only, writable
