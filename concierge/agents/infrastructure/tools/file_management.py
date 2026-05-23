from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from concierge.agents.infrastructure.tools.exceptions import FileToolError
from concierge.loggers import get_logger

logger = get_logger(__name__)

FILE_TOOL_NAMES: tuple[str, ...] = (
    "read_file",
    "list_directory",
    "file_search",
    "write_file",
    "copy_file",
    "move_file",
    "delete_file",
)


def resolve_file_root_dir(root_dir: str) -> Path:
    base = Path.cwd()
    configured = root_dir.strip()
    raw_path = Path(configured) if configured else base / "workspace"
    if not raw_path.is_absolute():
        raw_path = base / raw_path
    resolved = raw_path.resolve(strict=False)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _safe_resolve(root_dir: Path, user_path: str) -> Path:
    input_path = Path(user_path)
    if input_path.is_absolute():
        raise ValueError("Absolute paths are not allowed.")
    resolved = (root_dir / input_path).resolve(strict=False)
    if not resolved.is_relative_to(root_dir):
        raise ValueError("Path escapes the configured workspace root.")
    return resolved


def _relative(root_dir: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root_dir).as_posix()


def _validate_glob_pattern(pattern: str) -> None:
    if Path(pattern).is_absolute():
        raise ValueError("Absolute patterns are not allowed.")
    if ".." in Path(pattern).parts:
        raise ValueError("Pattern cannot contain '..'.")


@dataclass(frozen=True)
class FileManagementCore:
    root_dir: Path

    @classmethod
    def from_root_dir(cls, root_dir: str) -> FileManagementCore:
        return cls(root_dir=resolve_file_root_dir(root_dir))

    def read_file(self, file_path: str) -> str:
        resolved = _safe_resolve(self.root_dir, file_path)
        if not resolved.exists() or not resolved.is_file():
            raise FileToolError(f"File not found: {file_path}")
        try:
            return resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise FileToolError(f"File is not valid UTF-8 text: {file_path}") from exc
        except OSError as exc:
            raise FileToolError(f"Failed to read file: {file_path}") from exc

    def list_directory(self, dir_path: str = ".") -> str:
        resolved = _safe_resolve(self.root_dir, dir_path)
        if not resolved.exists() or not resolved.is_dir():
            raise FileToolError(f"Directory not found: {dir_path}")
        entries = sorted(
            (
                f"{_relative(self.root_dir, entry)}/" if entry.is_dir() else _relative(self.root_dir, entry)
                for entry in resolved.iterdir()
            ),
        )
        return "\n".join(entries)

    def file_search(self, pattern: str, dir_path: str = ".") -> str:
        _validate_glob_pattern(pattern)
        directory = _safe_resolve(self.root_dir, dir_path)
        if not directory.exists() or not directory.is_dir():
            raise FileToolError(f"Directory not found: {dir_path}")

        matches: list[str] = []
        for path in directory.glob(pattern):
            resolved = path.resolve(strict=False)
            if resolved.is_relative_to(self.root_dir):
                matches.append(_relative(self.root_dir, resolved))
        return "\n".join(sorted(set(matches)))

    def write_file(self, file_path: str, text: str) -> str:
        started_at = perf_counter()
        result = "failed"
        try:
            resolved = _safe_resolve(self.root_dir, file_path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(text, encoding="utf-8")
            result = "succeeded"
            return f"File written successfully: {file_path}"
        except (ValueError, OSError) as exc:
            raise FileToolError(f"Failed to write file: {file_path}") from exc
        finally:
            self._log_write_operation("write_file", file_path, result, started_at)

    def copy_file(self, source_path: str, destination_path: str) -> str:
        started_at = perf_counter()
        result = "failed"
        try:
            source = _safe_resolve(self.root_dir, source_path)
            destination = _safe_resolve(self.root_dir, destination_path)
            if not source.exists() or not source.is_file():
                raise FileToolError(f"File not found: {source_path}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            result = "succeeded"
            return f"File copied successfully: {source_path} -> {destination_path}"
        except OSError as exc:
            raise FileToolError("Failed to copy file.") from exc
        finally:
            self._log_write_operation("copy_file", f"{source_path} -> {destination_path}", result, started_at)

    def move_file(self, source_path: str, destination_path: str) -> str:
        started_at = perf_counter()
        result = "failed"
        try:
            source = _safe_resolve(self.root_dir, source_path)
            destination = _safe_resolve(self.root_dir, destination_path)
            if not source.exists() or not source.is_file():
                raise FileToolError(f"File not found: {source_path}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            result = "succeeded"
            return f"File moved successfully: {source_path} -> {destination_path}"
        except ValueError as exc:
            raise FileToolError("Failed to move file.") from exc
        except OSError as exc:
            raise FileToolError("Failed to move file.") from exc
        finally:
            self._log_write_operation("move_file", f"{source_path} -> {destination_path}", result, started_at)

    def delete_file(self, file_path: str) -> str:
        started_at = perf_counter()
        result = "failed"
        try:
            resolved = _safe_resolve(self.root_dir, file_path)
            if not resolved.exists() or not resolved.is_file():
                raise FileToolError(f"File not found: {file_path}")
            resolved.unlink()
            result = "succeeded"
            return f"File deleted successfully: {file_path}"
        except ValueError as exc:
            raise FileToolError("Failed to delete file.") from exc
        except OSError as exc:
            raise FileToolError("Failed to delete file.") from exc
        finally:
            self._log_write_operation("delete_file", file_path, result, started_at)

    @staticmethod
    def _log_write_operation(operation: str, path: str, result: str, started_at: float) -> None:
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        logger.info("file_tool=%s path=%s result=%s elapsed_ms=%s", operation, path, result, elapsed_ms)
