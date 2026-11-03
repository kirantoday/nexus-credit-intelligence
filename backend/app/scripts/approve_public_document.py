"""Operator tool: approve (or revoke) a research document for public
retrieval and external embedding (Milestone 10D.2, ADR-021).

    python -m app.scripts.approve_public_document approve \\
        --research-document-id <uuid> --derived-sha256 <sha256-of-the-pdf> \\
        --source-url <url> --source-sha256 <sha256-of-original> \\
        --converter-name <name> --converter-version <version> \\
        --page-reference-basis converted_pdf \\
        --approval-basis "<why this document is public>" --approved-by <name> [--confirm]

    python -m app.scripts.approve_public_document revoke \\
        --approval-id <uuid> --revoked-by <name> [--confirm]

This is the **only** way an approval is created. No API route exists, and
no request parameter can add to the allowlist. Without `--confirm` the
command only reads and reports what it would do; with it, it writes the
approval and an `audit_event` in one transaction.

`approve` requires the operator to supply the SHA-256 of the exact file
they intend to approve, and refuses unless that equals the checksum the
system recorded when the document was uploaded — so an approval can only
ever bind to the file the operator actually reviewed.

**Running this against the shared database is a separate approval** (see
the 10D database approval plan); nothing in 10D.2 executes it.
"""

from __future__ import annotations

import argparse
import sys
import uuid


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="approve_public_document")
    sub = parser.add_subparsers(dest="command", required=True)

    approve = sub.add_parser("approve")
    approve.add_argument("--research-document-id", type=uuid.UUID, required=True)
    approve.add_argument("--derived-sha256", required=True)
    approve.add_argument("--source-url", required=True)
    approve.add_argument("--source-sha256", default=None)
    approve.add_argument("--converter-name", default=None)
    approve.add_argument("--converter-version", default=None)
    approve.add_argument(
        "--page-reference-basis", choices=["original", "converted_pdf"], required=True
    )
    approve.add_argument("--approval-basis", required=True)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--confirm", action="store_true")

    revoke = sub.add_parser("revoke")
    revoke.add_argument("--approval-id", type=uuid.UUID, required=True)
    revoke.add_argument("--revoked-by", required=True)
    revoke.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)

    from app.core.types import AuditEventType, PageReferenceBasis
    from app.db.session import SessionLocal
    from app.domain.audit import AuditEventCreate
    from app.domain.public_document_approval import PublicDocumentApprovalCreate
    from app.repositories import (
        audit_repository,
        public_document_approval_repository,
        raw_provider_payload_repository,
        research_document_repository,
    )

    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        if args.command == "approve":
            document = research_document_repository.get_document(db, args.research_document_id)
            if document is None:
                print("ERROR: research_document not found.", file=sys.stderr)
                return 1
            payload = raw_provider_payload_repository.get_payload(db, document.raw_payload_id)
            if payload is None or payload.checksum != args.derived_sha256:
                print(
                    "ERROR: --derived-sha256 does not match the checksum recorded for the "
                    "stored file; refusing to approve a file that was not reviewed.",
                    file=sys.stderr,
                )
                return 1
            data = PublicDocumentApprovalCreate(
                research_document_id=args.research_document_id,
                approved_raw_payload_checksum=args.derived_sha256,
                source_url=args.source_url,
                source_sha256=args.source_sha256,
                converter_name=args.converter_name,
                converter_version=args.converter_version,
                page_reference_basis=PageReferenceBasis(args.page_reference_basis),
                approval_basis=args.approval_basis,
                approved_by=args.approved_by,
            )
            if not args.confirm:
                print("DRY RUN: would approve this document. Re-run with --confirm to write.")
                return 0
            approval = public_document_approval_repository.create_approval(db, data)
            audit_repository.create_event(
                db,
                AuditEventCreate(
                    user_id=args.approved_by,
                    event_type=AuditEventType.PUBLIC_DOCUMENT_APPROVED.value,
                    entity_table="public_document_approval",
                    entity_id=approval.id,
                    before_state=None,
                    after_state={
                        "research_document_id": str(args.research_document_id),
                        "page_reference_basis": args.page_reference_basis,
                        "source_url": args.source_url,
                    },
                ),
            )
            db.commit()
            print(f"Approved: public_document_approval {approval.id}")
            return 0

        approval_id: uuid.UUID = args.approval_id
        if not args.confirm:
            print("DRY RUN: would revoke this approval. Re-run with --confirm to write.")
            return 0
        revoked = public_document_approval_repository.revoke_approval(
            db, approval_id, revoked_by=args.revoked_by
        )
        if revoked is None:
            print("ERROR: approval not found.", file=sys.stderr)
            return 1
        audit_repository.create_event(
            db,
            AuditEventCreate(
                user_id=args.revoked_by,
                event_type=AuditEventType.PUBLIC_DOCUMENT_APPROVAL_REVOKED.value,
                entity_table="public_document_approval",
                entity_id=revoked.id,
                before_state={"revoked": False},
                after_state={"revoked": True},
            ),
        )
        db.commit()
        print(f"Revoked: public_document_approval {revoked.id}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
