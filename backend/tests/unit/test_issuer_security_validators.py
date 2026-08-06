"""Unit tests for the `is_synthetic`/`synthetic_reason` validators on
`IssuerCreate` and `SecurityCreate` (PLAN.md 4.5's synthetic_flag pattern).

Mirrors the DB CHECK constraints in app/models/issuer.py and
app/models/security.py — see ARCHITECTURE_DECISIONS.md ADR-014.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.types import InstrumentType
from app.domain.issuer import IssuerCreate
from app.domain.security import SecurityCreate


def test_issuer_synthetic_reason_requires_is_synthetic() -> None:
    with pytest.raises(ValidationError, match="synthetic_reason may only be set"):
        IssuerCreate(
            legal_name="Fictional Co",
            is_synthetic=False,
            synthetic_reason="SYNTHETIC_DEMO_DATA",
            provenance_id=uuid4(),
        )


def test_issuer_synthetic_with_reason_is_valid() -> None:
    IssuerCreate(
        legal_name="Fictional Co",
        is_synthetic=True,
        synthetic_reason="SYNTHETIC_DEMO_DATA",
        provenance_id=uuid4(),
    )


def test_issuer_non_synthetic_without_reason_is_valid() -> None:
    IssuerCreate(legal_name="Apple Inc.", is_synthetic=False, provenance_id=uuid4())


def test_issuer_defaults_to_not_synthetic() -> None:
    issuer = IssuerCreate(legal_name="Apple Inc.", provenance_id=uuid4())
    assert issuer.is_synthetic is False
    assert issuer.synthetic_reason is None


def _base_security_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = dict(
        issuer_id=uuid4(),
        instrument_type=InstrumentType.LOAN,
        description="Test Co — First Lien Term Loan B due 2029",
        provenance_id=uuid4(),
    )
    defaults.update(overrides)
    return defaults


def test_security_synthetic_reason_requires_is_synthetic() -> None:
    with pytest.raises(ValidationError, match="synthetic_reason may only be set"):
        SecurityCreate(
            **_base_security_kwargs(is_synthetic=False, synthetic_reason="SYNTHETIC_DEMO_DATA")  # type: ignore[arg-type]
        )


def test_security_synthetic_with_reason_is_valid() -> None:
    SecurityCreate(
        **_base_security_kwargs(is_synthetic=True, synthetic_reason="SYNTHETIC_DEMO_DATA")  # type: ignore[arg-type]
    )


def test_security_non_synthetic_without_reason_is_valid() -> None:
    SecurityCreate(**_base_security_kwargs())  # type: ignore[arg-type]


def test_security_defaults_to_not_synthetic() -> None:
    security = SecurityCreate(**_base_security_kwargs())  # type: ignore[arg-type]
    assert security.is_synthetic is False
    assert security.synthetic_reason is None
