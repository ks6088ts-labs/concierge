from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from concierge.agents.infrastructure.tools.exceptions import ShellToolError
from concierge.loggers import get_logger

logger = get_logger(__name__)

SHELL_TOOL_NAMES: tuple[str, ...] = ("shell_exec",)
_SHELL_ENV_KEEP: tuple[str, ...] = ("HOME", "PATH", "LANG")
_SHELL_ENV_PREFIX_KEEP: tuple[str, ...] = ("TF_",)


def resolve_shell_root_dir(root_dir: str, fallback: str) -> Path:
    base = Path.cwd()
    configured = root_dir.strip() or fallback.strip()
    raw_path = Path(configured) if configured else base / "workspace"
    if not raw_path.is_absolute():
        raw_path = base / raw_path
    resolved = raw_path.resolve(strict=False)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _sanitize_env() -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in _SHELL_ENV_KEEP or any(key.startswith(prefix) for prefix in _SHELL_ENV_PREFIX_KEEP):
            sanitized[key] = value
    return sanitized


def _truncate_output(raw: bytes, max_output_bytes: int) -> str:
    if len(raw) <= max_output_bytes:
        return raw.decode("utf-8", errors="replace")
    suffix = f"... [truncated {len(raw) - max_output_bytes} bytes]"
    return f"{raw[:max_output_bytes].decode('utf-8', errors='replace')}{suffix}"


@dataclass(frozen=True)
class ShellCommandConfig:
    allowed_commands: tuple[str, ...]
    root_dir: Path
    timeout_seconds: int = 30
    max_output_bytes: int = 65536


@dataclass(frozen=True)
class ShellCommandCore:
    config: ShellCommandConfig

    def shell_exec(self, command: str | list[str]) -> str:
        argv = self._to_argv(command)
        command_name = self._validate_command(argv[0])
        started_at = perf_counter()
        exit_code = -1
        try:
            completed = subprocess.run(
                argv,
                shell=False,
                cwd=self.config.root_dir,
                capture_output=True,
                timeout=self.config.timeout_seconds,
                check=False,
                env=_sanitize_env(),
            )
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            raise ShellToolError(f"Timed out after {self.config.timeout_seconds} s.") from exc
        except OSError as exc:
            raise ShellToolError(f"Failed to execute command: {command_name}") from exc
        finally:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            logger.info(
                "operation=shell_exec command=%s exit_code=%s elapsed_ms=%s",
                command_name,
                exit_code,
                elapsed_ms,
            )

        stdout = _truncate_output(completed.stdout, self.config.max_output_bytes)
        stderr = _truncate_output(completed.stderr, self.config.max_output_bytes)
        return f"exit_code: {completed.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"

    @staticmethod
    def _to_argv(command: str | list[str]) -> list[str]:
        if isinstance(command, str):
            try:
                argv = shlex.split(command)
            except ValueError as exc:
                raise ShellToolError("Failed to parse command string.") from exc
        else:
            argv = [str(part) for part in command]
        if not argv:
            raise ShellToolError("Command must not be empty.")
        return argv

    def _validate_command(self, command_name: str) -> str:
        if not command_name.strip():
            raise ShellToolError("Command must not be empty.")
        if Path(command_name).name != command_name:
            raise ShellToolError("Command paths are not allowed; use the command name only.")
        if command_name not in self.config.allowed_commands:
            raise ShellToolError(f"Command not allowed: {command_name}")
        return command_name
