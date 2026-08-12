"""Unit tests for `app/services/research_document_service.py`'s pure
validation/generation functions (PLAN.md 4.10; Milestone 10B).

No database, no Storage — PDF magic-byte validation, size limit, filename
sanitization, and storage-key generation are all exhaustively testable
without I/O.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.research_document_service import (
    MAX_UPLOAD_SIZE_BYTES,
    FileTooLargeError,
    InvalidPdfError,
    _validate_pdf,
    _validate_size,
    build_storage_key,
    sanitize_filename,
)


def test_valid_pdf_signature_passes() -> None:
    _validate_pdf(b"%PDF-1.4\n...")


def test_non_pdf_content_is_rejected() -> None:
    with pytest.raises(InvalidPdfError):
        _validate_pdf(b"this is not a pdf, just text pretending to be one")


def test_pdf_extension_alone_does_not_pass_content_check() -> None:
    """A file whose bytes don't start with %PDF- is rejected even if a
    caller claims it's a PDF via filename/Content-Type — those are never
    trusted (approved architecture, item 2)."""
    with pytest.raises(InvalidPdfError):
        _validate_pdf(b"<html><body>fake.pdf</body></html>")


def test_empty_content_is_rejected() -> None:
    with pytest.raises(InvalidPdfError):
        _validate_pdf(b"")


def test_file_within_limit_passes() -> None:
    _validate_size(b"%PDF-" + b"0" * 1024)


def test_file_at_exact_limit_passes() -> None:
    _validate_size(b"0" * MAX_UPLOAD_SIZE_BYTES)


def test_file_over_limit_is_rejected() -> None:
    with pytest.raises(FileTooLargeError) as exc_info:
        _validate_size(b"0" * (MAX_UPLOAD_SIZE_BYTES + 1))
    assert exc_info.value.size_bytes == MAX_UPLOAD_SIZE_BYTES + 1


def test_sanitize_filename_strips_control_and_path_characters() -> None:
    # `/`, `"`, `:`, `*`, `?`, `<`, `>`, `|`, and control/null bytes are all
    # stripped (unsafe as a storage key or in a Content-Disposition header);
    # `;`, `-`, and spaces are ordinary characters and pass through
    # unchanged — this is filename sanitization for safe display/download,
    # not a storage key (which is always a UUID, never derived from this).
    assert sanitize_filename('../../etc/passwd"; rm -rf /\x00.pdf') == "....etcpasswd; rm -rf .pdf"


def test_sanitize_filename_preserves_ordinary_names() -> None:
    name = "Trinseo Credit Agreement 2026.pdf"
    assert sanitize_filename(name) == name


def test_sanitize_filename_falls_back_when_empty_after_stripping() -> None:
    assert sanitize_filename("\x00\x00\x00") == "document.pdf"


def test_sanitize_filename_caps_length() -> None:
    long_name = ("a" * 400) + ".pdf"
    result = sanitize_filename(long_name)
    assert len(result) == 255


def test_storage_key_uses_document_id_never_filename() -> None:
    issuer_id = uuid4()
    document_id = uuid4()
    key = build_storage_key(issuer_id, document_id)
    assert key == f"research-documents/{issuer_id}/{document_id}/{document_id}.pdf"


def test_storage_key_is_deterministic_for_same_ids() -> None:
    issuer_id = uuid4()
    document_id = uuid4()
    assert build_storage_key(issuer_id, document_id) == build_storage_key(issuer_id, document_id)
