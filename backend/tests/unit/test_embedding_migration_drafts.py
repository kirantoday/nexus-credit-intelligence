"""Structural guard for the draft Milestone 10D migrations (10D.2).

Drafts live in `alembic/drafts/` so Alembic cannot discover — and an
unrelated `alembic upgrade head` cannot apply — them. These checks parse
the files with `ast`/text only (no database, no Alembic runtime) and fail
if a draft is promoted by accident, the revision chain breaks, a draft
touches an extension or a non-`nexus` schema, a downgrade forgets a table,
or the draft vector width drifts from the application's contract.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.embeddings.dimensions import EMBEDDING_COLUMN_DIMENSION

_ALEMBIC = Path(__file__).resolve().parents[2] / "alembic"
_VERSIONS = _ALEMBIC / "versions"
_DRAFTS = _ALEMBIC / "drafts"
_DRAFT_FILES = {"0021": "0021_public_document_approval.py", "0022": "0022_document_embeddings.py"}
_SCHEMA_CALLS = {"create_table", "drop_table", "create_index", "drop_index"}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _module_str(tree: ast.Module, name: str) -> str | None:
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name:
            value = node.value
            return value.value if isinstance(value, ast.Constant) else None
    return None


def _op_calls(tree: ast.Module, function: str) -> list[ast.Call]:
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    return [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "op"
    ]


def test_drafts_are_not_in_the_discovered_versions_directory() -> None:
    discovered = {p.name for p in _VERSIONS.glob("*.py")}
    for filename in _DRAFT_FILES.values():
        assert filename not in discovered
    assert not any(name.startswith(("0021", "0022")) for name in discovered)


def test_discovered_head_is_still_0020() -> None:
    revisions = sorted(p.name[:4] for p in _VERSIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))
    assert revisions[-1] == "0020"


def test_draft_revision_chain_extends_the_current_head() -> None:
    chain = {}
    for revision, filename in _DRAFT_FILES.items():
        tree = _tree(_DRAFTS / filename)
        assert _module_str(tree, "revision") == revision
        chain[revision] = _module_str(tree, "down_revision")
    assert chain == {"0021": "0020", "0022": "0021"}


def test_every_draft_has_upgrade_and_downgrade() -> None:
    for filename in _DRAFT_FILES.values():
        names = {n.name for n in _tree(_DRAFTS / filename).body if isinstance(n, ast.FunctionDef)}
        assert {"upgrade", "downgrade"} <= names


def test_drafts_only_touch_the_nexus_schema() -> None:
    for filename in _DRAFT_FILES.values():
        tree = _tree(_DRAFTS / filename)
        for function in ("upgrade", "downgrade"):
            for call in _op_calls(tree, function):
                if call.func.attr in _SCHEMA_CALLS:  # type: ignore[attr-defined]
                    schema = next((k.value for k in call.keywords if k.arg == "schema"), None)
                    assert isinstance(schema, ast.Constant) and schema.value == "nexus"


def test_drafts_never_create_alter_or_drop_extensions_or_other_schemas() -> None:
    forbidden = re.compile(
        r"(CREATE|ALTER|DROP)\s+(EXTENSION|SCHEMA)|schema\s*=\s*[\"'](?!nexus)", re.IGNORECASE
    )
    for filename in _DRAFT_FILES.values():
        text = (_DRAFTS / filename).read_text(encoding="utf-8")
        # Docstrings legitimately mention the extension; only executable
        # statements matter, so strip the module docstring first.
        body = text.split('"""', 2)[-1]
        assert not forbidden.search(body), filename


def test_foreign_keys_reference_only_nexus_tables() -> None:
    for filename in _DRAFT_FILES.values():
        text = (_DRAFTS / filename).read_text(encoding="utf-8")
        for target in re.findall(r"ForeignKeyConstraint\(\[[^\]]*\],\s*\[\"([^\"]+)\"\]", text):
            assert target.startswith("nexus."), target


def test_downgrades_drop_exactly_the_tables_upgrades_create() -> None:
    for filename in _DRAFT_FILES.values():
        tree = _tree(_DRAFTS / filename)

        def tables(function: str, call_name: str, tree: ast.Module = tree) -> set[str]:
            return {
                c.args[0].value  # type: ignore[attr-defined]
                for c in _op_calls(tree, function)
                if c.func.attr == call_name  # type: ignore[attr-defined]
            }

        assert tables("upgrade", "create_table") == tables("downgrade", "drop_table")
        assert tables("upgrade", "create_table")


def test_draft_vector_width_matches_the_application_contract() -> None:
    text = (_DRAFTS / _DRAFT_FILES["0022"]).read_text(encoding="utf-8")
    match = re.search(r"^EMBEDDING_DIMENSION\s*=\s*(\d+)", text, re.MULTILINE)
    assert match is not None
    assert int(match.group(1)) == EMBEDDING_COLUMN_DIMENSION
    assert "DRAFT" in text.split('"""', 2)[1]
