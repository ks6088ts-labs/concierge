"""Architecture tests for concierge.agents - verifies DDD layer boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

FRAMEWORK_IMPORTS = {
    "fastapi",
    "pydantic",
    "typer",
    "uvicorn",
    "httpx",
    "sqlalchemy",
    "psycopg",
    "azure",
    "langchain",
    "langgraph",
    "langchain_core",
    "langchain_azure_ai",
    "agent_framework",
    "copilot",
}
BASE_PATH = Path("concierge/agents")


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


def test_application_has_no_infrastructure_imports() -> None:
    for file in _iter_python_files(BASE_PATH / "application"):
        imports = _imported_modules(file)
        assert not any(module.startswith("concierge.agents.infrastructure") for module in imports), file


def test_agents_does_not_depend_on_bounded_contexts() -> None:
    forbidden_prefixes = ("concierge.todo", "concierge.chat", "concierge.cloud_agent")
    for file in _iter_python_files(BASE_PATH):
        imports = _imported_modules(file)
        offending = [m for m in imports if any(m.startswith(p) for p in forbidden_prefixes)]
        assert not offending, f"{file}: {offending}"
