"""The entitlement engine: `policy_check`, the single choke point for licensed data.

Per PLAN.md section 4.8 and CLAUDE.md's Provenance and Entitlement Rules: no
licensed content may be displayed, exported, sent to an LLM, embedded, included
in a prompt, downloaded as a document, or exposed via the API without a passing
`policy_check` for that specific action. `policy_check` is a pure function —
it takes an already-resolved `DataEntitlement` (looked up by the caller via
`app.repositories.entitlement_repository`) and makes no I/O of its own, which
is what makes it exhaustively unit-testable without a database.

Action -> entitlement permission flag mapping. `data_entitlement` has one
permission flag per broad capability, not one per action, so several actions
share a flag by design:

- `display` -> `display_permission` (direct 1:1)
- `export` -> `redistribution_permission` (taking data out of the system)
- `document_download` -> `redistribution_permission` (a raw document leaving
  the system is the same concern as `export`)
- `api_expose` -> `redistribution_permission` (exposing to external API
  consumers)
- `send_to_llm` -> `ai_processing_permission` (broad "used in AI processing"
  grant)
- `prompt_inclusion` -> `ai_processing_permission` (still AI processing, not a
  persisted artifact)
- `create_embedding` -> `embedding_permission` (narrower than AI processing:
  creates a durable, searchable pgvector row)

`derived_data_permission` governs whether *calculated* values derived from
licensed inputs may be treated less restrictively than the raw input itself —
that requires walking `calculation_input` lineage back to the strictest
governing entitlement, which is out of scope until a real licensed provider
exists (Milestone 14+). `storage_allowed` and `retention_period_days` gate
ingestion, not read-time access, so they are enforced where raw payloads are
persisted, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.types import DataClassification, EntitlementAction
from app.domain.entitlement import DataEntitlement

_ACTION_PERMISSION_FIELDS: dict[EntitlementAction, str] = {
    EntitlementAction.DISPLAY: "display_permission",
    EntitlementAction.EXPORT: "redistribution_permission",
    EntitlementAction.SEND_TO_LLM: "ai_processing_permission",
    EntitlementAction.CREATE_EMBEDDING: "embedding_permission",
    EntitlementAction.PROMPT_INCLUSION: "ai_processing_permission",
    EntitlementAction.DOCUMENT_DOWNLOAD: "redistribution_permission",
    EntitlementAction.API_EXPOSE: "redistribution_permission",
}


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Request-time facts `policy_check` needs beyond the entitlement itself.

    A plain dataclass, not a Pydantic domain object: this is a call-time
    parameter bundle for the policy engine, not a canonical business entity a
    provider populates or a repository persists.
    """

    environment: str
    requested_by_user_id: str | None = None
    now: datetime | None = None


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """The result of a `policy_check` call. Truthy iff `allowed`."""

    allowed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.allowed


def policy_check(
    action: EntitlementAction,
    classification: DataClassification,
    entitlement: DataEntitlement | None,
    context: PolicyContext,
) -> PolicyDecision:
    """Decide whether `action` may be performed on data of `classification`.

    Public, synthetic, and AI-extracted data carry no license restriction and
    are always allowed. Licensed data requires an active `DataEntitlement`
    whose environment matches, whose effective/expiration window covers the
    current date, whose `permitted_users` allow-list (if set) includes the
    requesting user, and whose permission flag for `action` is set.
    """
    if classification is not DataClassification.LICENSED:
        return PolicyDecision(True, f"'{classification.value}' data carries no license restriction")

    if entitlement is None:
        return PolicyDecision(False, "no data_entitlement on file for this licensed data")

    if entitlement.environment.value != context.environment:
        return PolicyDecision(
            False,
            f"entitlement is scoped to environment '{entitlement.environment.value}', "
            f"not '{context.environment}'",
        )

    today = (context.now or datetime.now(UTC)).date()

    if today < entitlement.effective_date:
        return PolicyDecision(False, "entitlement is not yet effective")

    if entitlement.expiration_date is not None and today > entitlement.expiration_date:
        return PolicyDecision(False, "entitlement has expired")

    if entitlement.permitted_users:
        if (
            context.requested_by_user_id is None
            or context.requested_by_user_id not in entitlement.permitted_users
        ):
            return PolicyDecision(
                False, "requesting user is not on the entitlement's permitted_users list"
            )

    permission_field = _ACTION_PERMISSION_FIELDS[action]
    if not getattr(entitlement, permission_field):
        return PolicyDecision(
            False,
            f"entitlement does not grant '{permission_field}', required for action "
            f"'{action.value}'",
        )

    return PolicyDecision(
        True, f"entitlement grants '{permission_field}' for action '{action.value}'"
    )
