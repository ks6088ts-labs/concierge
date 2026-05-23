from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from concierge.agents.infrastructure.tools.exceptions import ShellToolError
from concierge.agents.infrastructure.tools.shell_command import (
    ShellCommandConfig,
    ShellCommandCore,
    resolve_shell_root_dir,
)


def test_resolve_shell_root_dir_falls_back_to_file_root(tmp_path: Path) -> None:
    fallback = tmp_path / "workspace"
    resolved = resolve_shell_root_dir("", str(fallback))
    assert resolved == fallback.resolve()
    assert resolved.exists()


def test_shell_exec_rejects_non_allowlisted_command(monkeypatch, tmp_path: Path) -> None:
    core = ShellCommandCore(
        config=ShellCommandConfig(
            allowed_commands=("terraform",),
            root_dir=tmp_path,
        )
    )
    called = {"run": False}

    def _fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        called["run"] = True
        return subprocess.CompletedProcess([], 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(ShellToolError, match="Command not allowed"):
        core.shell_exec("echo hello")
    assert called["run"] is False


def test_shell_exec_disables_shell_chaining(monkeypatch, tmp_path: Path) -> None:
    core = ShellCommandCore(
        config=ShellCommandConfig(
            allowed_commands=("echo",),
            root_dir=tmp_path,
        )
    )
    captured: dict[str, Any] = {}

    def _fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, b"ok", b"")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = core.shell_exec("echo hello; whoami | cat && pwd > out.txt")

    assert captured["argv"] == ["echo", "hello;", "whoami", "|", "cat", "&&", "pwd", ">", "out.txt"]
    assert captured["kwargs"]["shell"] is False
    assert "exit_code: 0" in result


def test_shell_exec_rejects_absolute_command_path(monkeypatch, tmp_path: Path) -> None:
    core = ShellCommandCore(
        config=ShellCommandConfig(
            allowed_commands=("terraform",),
            root_dir=tmp_path,
        )
    )

    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: pytest.fail("subprocess.run must not be called"))
    with pytest.raises(ShellToolError, match="paths are not allowed"):
        core.shell_exec("/usr/bin/terraform version")


def test_shell_exec_uses_fixed_cwd(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    core = ShellCommandCore(
        config=ShellCommandConfig(
            allowed_commands=("python3",),
            root_dir=root,
        )
    )
    result = core.shell_exec('python3 -c "import os; print(os.getcwd())"')
    assert str(root.resolve()) in result


def test_shell_exec_timeout(tmp_path: Path) -> None:
    core = ShellCommandCore(
        config=ShellCommandConfig(
            allowed_commands=("python3",),
            root_dir=tmp_path,
            timeout_seconds=1,
        )
    )
    with pytest.raises(ShellToolError, match="Timed out"):
        core.shell_exec('python3 -c "import time; time.sleep(2)"')


def test_shell_exec_output_truncation(tmp_path: Path) -> None:
    core = ShellCommandCore(
        config=ShellCommandConfig(
            allowed_commands=("python3",),
            root_dir=tmp_path,
            max_output_bytes=16,
        )
    )
    result = core.shell_exec('python3 -c "print(\'x\' * 128)"')
    assert "[truncated" in result
