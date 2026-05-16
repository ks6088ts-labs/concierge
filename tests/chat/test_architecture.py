from __future__ import annotations

import ast
from pathlib import Path

FRAMEWORK_IMPORTS = {"fastapi", "pydantic", "typer", "uvicorn", "httpx", "sqlalchemy", "psycopg", "azure", "websockets"}
BASE_PATH = Path("concierge/chat")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                modules.add(name.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _iter_python_files(path: Path):
    for file in path.rglob("*.py"):
        if file.name == "__init__.py":
            continue
        yield file


def test_domain_has_no_framework_imports() -> None:
    for file in _iter_python_files(BASE_PATH / "domain"):
        imports = _imported_modules(file)
        assert not any(module.split(".")[0] in FRAMEWORK_IMPORTS for module in imports), file


def test_application_has_no_framework_or_infrastructure_imports() -> None:
    for file in _iter_python_files(BASE_PATH / "application"):
        imports = _imported_modules(file)
        assert not any(module.split(".")[0] in FRAMEWORK_IMPORTS for module in imports), file
        assert not any(module.startswith("concierge.chat.infrastructure") for module in imports), file


def test_foundry_realtime_does_not_import_web() -> None:
    """foundry_realtime.py must not import from the web infrastructure layer."""
    realtime_file = BASE_PATH / "infrastructure" / "ai" / "foundry_realtime.py"
    imports = _imported_modules(realtime_file)
    assert not any(module.startswith("concierge.chat.infrastructure.web") for module in imports), realtime_file
