"""Source-level guard for the inert draft revision 0023 (embedding job
scheduling). It reads the draft and the SQLAlchemy model as text/AST and
metadata; it renders no SQL, connects to nothing and proves nothing about a
live database (lock durations, rollback, existing-row behavior are unverified
until a read-only preflight and an approved test environment)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.core.types import EmbeddingJobStatus
from app.db.base import Base

_ALEMBIC = Path(__file__).resolve().parents[2] / "alembic"
_DRAFT = _ALEMBIC / "drafts" / "0023_embedding_job_scheduling.py"
_DRAFT_0022 = _ALEMBIC / "drafts" / "0022_document_embeddings.py"
_VERSIONS = _ALEMBIC / "versions"
_README = _ALEMBIC / "drafts" / "README.md"
_NEW_COLUMNS = {
    "retry_not_before",
    "provider_wide",
    "hold_reason",
    "held_at",
    "released_at",
    "released_by",
}
_NEW_CHECKS = {
    "ck_document_embedding_job_held_has_reason",
    "ck_document_embedding_job_delay_only_when_pending",
    "ck_document_embedding_job_provider_wide_only_pending_or_held",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _assigned_str(tree: ast.Module, name: str) -> str | None:
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name:
            return node.value.value if isinstance(node.value, ast.Constant) else None  # type: ignore[union-attr]
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


def _first_str_args(calls: list[ast.Call], attr: str, index: int) -> set[str]:
    out: set[str] = set()
    for call in calls:
        if call.func.attr == attr:  # type: ignore[attr-defined]
            arg = call.args[index]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.add(arg.value)
    return out


def _column_names(call: ast.Call) -> set[str]:
    return {
        arg.args[0].value  # type: ignore[attr-defined]
        for arg in call.args
        if isinstance(arg, ast.Call)
        and isinstance(arg.func, ast.Attribute)
        and arg.func.attr == "Column"
    }


def test_the_draft_is_inert_and_chains_from_0022() -> None:
    tree = _tree(_DRAFT)
    assert _assigned_str(tree, "revision") == "0023"
    assert _assigned_str(tree, "down_revision") == "0022"
    assert not any(p.name.startswith("0023") for p in _VERSIONS.glob("*.py"))
    assert sorted(p.name[:4] for p in _VERSIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))[-1] == "0020"


def test_the_existing_drafts_are_not_modified_by_the_new_revision() -> None:
    # 0022 may already have been applied somewhere; the new work is its own
    # revision. 0022 must still create the job table without the new columns.
    tree = _tree(_DRAFT_0022)
    created = {
        name
        for call in _op_calls(tree, "upgrade")
        if call.func.attr == "create_table"  # type: ignore[attr-defined]
        and call.args[0].value == "document_embedding_job"  # type: ignore[attr-defined]
        for name in _column_names(call)
    }
    assert created and not (created & _NEW_COLUMNS)


def test_every_operation_targets_the_nexus_schema_only() -> None:
    tree = _tree(_DRAFT)
    for function in ("upgrade", "downgrade"):
        for call in _op_calls(tree, function):
            if call.func.attr in {"execute"}:  # type: ignore[attr-defined]
                continue
            schema = next((k.value for k in call.keywords if k.arg == "schema"), None)
            assert isinstance(schema, ast.Constant) and schema.value == "nexus", call.func.attr  # type: ignore[attr-defined]
    body = _DRAFT.read_text(encoding="utf-8").split('"""', 2)[-1]
    assert not re.search(r"(CREATE|ALTER|DROP)\s+(EXTENSION|SCHEMA)", body, re.IGNORECASE)
    assert "public." not in body and "CREATE TABLE" not in body.upper()


def test_only_the_job_table_is_touched() -> None:
    tree = _tree(_DRAFT)
    positions = {
        "add_column": 0,
        "drop_column": 0,
        "create_index": 1,
        "create_check_constraint": 1,
        "drop_constraint": 1,
    }
    seen = set()
    for function in ("upgrade", "downgrade"):
        for call in _op_calls(tree, function):
            name = call.func.attr  # type: ignore[attr-defined]
            if name in positions:
                seen.add(ast.unparse(call.args[positions[name]]))
            if name == "drop_index":
                seen.add(ast.unparse(next(k.value for k in call.keywords if k.arg == "table_name")))
    assert seen == {"_TABLE"}
    table = next(
        n.value.value  # type: ignore[attr-defined]
        for n in tree.body
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "_TABLE"
    )
    assert table == "document_embedding_job"


def test_the_added_columns_match_the_model() -> None:
    tree = _tree(_DRAFT)
    added = set()
    for call in _op_calls(tree, "upgrade"):
        if call.func.attr == "add_column":  # type: ignore[attr-defined]
            added |= _column_names_from_add(call)
    assert added == _NEW_COLUMNS
    model_columns = {c.name for c in Base.metadata.tables["nexus.document_embedding_job"].columns}
    assert _NEW_COLUMNS <= model_columns
    downgrade = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade"
    )
    dropped = {
        element.value
        for loop in ast.walk(downgrade)
        if isinstance(loop, ast.For) and isinstance(loop.iter, ast.Tuple)
        for element in loop.iter.elts
        if isinstance(element, ast.Constant)
    }
    assert dropped == _NEW_COLUMNS  # the downgrade removes exactly what the upgrade added


def _column_names_from_add(call: ast.Call) -> set[str]:
    column = call.args[1]
    assert isinstance(column, ast.Call)
    first = column.args[0]
    assert isinstance(first, ast.Constant)
    return {first.value}


def test_constraints_and_indexes_match_the_model_and_include_held() -> None:
    table = Base.metadata.tables["nexus.document_embedding_job"]
    model_checks = {c.name for c in table.constraints if c.name}
    assert _NEW_CHECKS <= model_checks and "ck_document_embedding_job_status" in model_checks
    tree = _tree(_DRAFT)
    created = _first_str_args(_op_calls(tree, "upgrade"), "create_check_constraint", 0)
    assert created == _NEW_CHECKS | {"ck_document_embedding_job_status"}
    text = _DRAFT.read_text(encoding="utf-8")
    assert "'held'" in text
    status_check = next(
        c for c in table.constraints if c.name == "ck_document_embedding_job_status"
    )
    assert "'held'" in str(status_check.sqltext)
    assert EmbeddingJobStatus.HELD.value == "held"
    unique = next(
        i for i in table.indexes if i.name == "ux_document_embedding_job_one_active_per_target"
    )
    assert "held" in str(unique.dialect_options["postgresql"]["where"])
    assert "ix_document_embedding_job_provider_wide" in {i.name for i in table.indexes}


def test_downgrade_refuses_to_silently_release_held_jobs() -> None:
    text = _DRAFT.read_text(encoding="utf-8")
    downgrade = text[text.index("def downgrade") :]
    assert "RAISE EXCEPTION" in downgrade and "status = 'held'" in downgrade
    # the guard runs before any destructive operation
    assert downgrade.index("RAISE EXCEPTION") < downgrade.index("drop_column")
    assert "UPDATE" not in downgrade.upper().split("RAISE EXCEPTION")[0]


def test_the_draft_documents_its_limits_and_activation_order() -> None:
    doc = ast.get_docstring(_tree(_DRAFT)) or ""
    for phrase in ("never be edited", "unverified", "0021, 0022 and 0023", "data loss"):
        assert phrase in doc.replace("\n", " "), phrase


def test_the_drafts_readme_lists_0023_as_unapplied_and_undiscovered() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "0023_embedding_job_scheduling.py" in text and "NOT applied" in text
