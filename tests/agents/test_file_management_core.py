from __future__ import annotations

import os
from pathlib import Path

import pytest

from concierge.agents.infrastructure.tools.exceptions import FileToolError
from concierge.agents.infrastructure.tools.file_management import FileManagementCore, resolve_file_root_dir


def test_read_list_and_search(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "hello.txt").write_text("hello", encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "app.py").write_text("print('ok')", encoding="utf-8")
    core = FileManagementCore.from_root_dir(str(root))

    assert core.read_file("hello.txt") == "hello"
    listed = core.list_directory(".")
    assert "hello.txt" in listed
    assert "nested/" in listed
    search = core.file_search("**/*.py")
    assert "nested/app.py" in search


def test_write_copy_move_delete(tmp_path: Path) -> None:
    core = FileManagementCore.from_root_dir(str(tmp_path / "workspace"))
    assert "written successfully" in core.write_file("a.txt", "abc")
    assert core.read_file("a.txt") == "abc"
    assert "copied successfully" in core.copy_file("a.txt", "b.txt")
    assert core.read_file("b.txt") == "abc"
    assert "moved successfully" in core.move_file("b.txt", "moved/b.txt")
    assert core.read_file("moved/b.txt") == "abc"
    assert "deleted successfully" in core.delete_file("moved/b.txt")
    with pytest.raises(FileToolError):
        core.read_file("moved/b.txt")


def test_rejects_path_traversal_and_absolute_path(tmp_path: Path) -> None:
    core = FileManagementCore.from_root_dir(str(tmp_path / "workspace"))
    with pytest.raises(ValueError, match="Absolute paths"):
        core.read_file(str((tmp_path / "workspace" / "a.txt").resolve()))
    with pytest.raises(ValueError, match="escapes"):
        core.read_file("../outside.txt")


@pytest.mark.skipif(os.name == "nt", reason="Symlink behavior differs on Windows")
def test_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    root.mkdir()
    outside.write_text("secret", encoding="utf-8")
    (root / "link.txt").symlink_to(outside)
    core = FileManagementCore.from_root_dir(str(root))
    with pytest.raises(ValueError, match="escapes"):
        core.read_file("link.txt")


def test_missing_file_errors(tmp_path: Path) -> None:
    core = FileManagementCore.from_root_dir(str(tmp_path / "workspace"))
    with pytest.raises(FileToolError, match="File not found"):
        core.read_file("missing.txt")
    with pytest.raises(FileToolError, match="File not found"):
        core.delete_file("missing.txt")


def test_root_dir_auto_created(tmp_path: Path) -> None:
    root = tmp_path / "new" / "workspace"
    assert not root.exists()
    resolved = resolve_file_root_dir(str(root))
    assert resolved.exists()
    assert resolved.is_dir()
