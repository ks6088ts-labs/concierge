from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "concierge" / "todo"
ALLOWED_IMPORTS = {
    "domain": {"domain"},
    "application": {"application", "domain"},
    "interfaces": {"interfaces", "application", "domain"},
    "infrastructure": {"infrastructure", "interfaces", "application", "domain"},
}
FORBIDDEN_DOMAIN_MODULES = {"fastapi", "pydantic", "typer", "mlflow", "opentelemetry", "azure"}


def test_todo_layers_only_import_allowed_internal_modules():
    for file_path in PACKAGE_ROOT.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue
        relative = file_path.relative_to(PACKAGE_ROOT)
        layer = relative.parts[0]
        if layer not in ALLOWED_IMPORTS:
            continue
        tree = ast.parse(file_path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if not node.module.startswith("concierge.todo."):
                continue
            imported_layer = node.module.split(".")[2]
            assert imported_layer in ALLOWED_IMPORTS[layer], f"{relative} imports disallowed layer {imported_layer}"


def test_domain_layer_avoids_framework_imports():
    for file_path in (PACKAGE_ROOT / "domain").rglob("*.py"):
        tree = ast.parse(file_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module.split(".")[0]]
            else:
                continue
            assert FORBIDDEN_DOMAIN_MODULES.isdisjoint(modules), f"{file_path.name} imports framework code"
