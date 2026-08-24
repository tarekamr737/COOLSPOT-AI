"""Architecture tests for the deterministic decision path."""

import ast
from pathlib import Path

DECISION_MODULES = (
    Path("api/app/services/feature_table.py"),
    Path("api/app/services/candidates.py"),
    Path("api/app/services/intervention_value.py"),
    Path("api/app/services/optimizer.py"),
)
FORBIDDEN_IMPORT_ROOTS = {
    "anthropic",
    "httpx",
    "httpx2",
    "litellm",
    "openai",
}
FORBIDDEN_MODULE = "api.app.services.explanations"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_decision_modules_do_not_import_llm_or_explanation_code() -> None:
    for path in DECISION_MODULES:
        imported = _imports(path)
        assert FORBIDDEN_MODULE not in imported
        assert not {name.split(".", maxsplit=1)[0] for name in imported} & (
            FORBIDDEN_IMPORT_ROOTS
        )
