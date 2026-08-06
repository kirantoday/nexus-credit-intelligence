"""Wraps `policy_check` for the AI evidence-review pipeline (PLAN.md 24.7).

SEC filing text is always `classification=public`, so this always passes for
this milestone's real usage — the call site still goes through it, so any
future evidence-provider whose content isn't public is gated for free, and no
evidence text ever reaches an LLM call without going through this choke point
(CLAUDE.md's "no licensed content may be ... sent to an LLM ... without a
passing policy_check").
"""

from __future__ import annotations

from app.core.entitlement import PolicyContext, PolicyDecision, policy_check
from app.core.types import DataClassification, EntitlementAction
from app.domain.entitlement import DataEntitlement


def check_send_to_llm(
    *,
    classification: DataClassification,
    entitlement: DataEntitlement | None,
    environment: str,
) -> PolicyDecision:
    """Must pass before any evidence text is included in a prompt or sent to
    the model. Checks both `prompt_inclusion` and `send_to_llm` — building
    the prompt and calling the model with it are the same event here, but
    both actions are checked independently so this stays correct if a future
    caller ever needs to build a prompt without immediately sending it.
    """
    context = PolicyContext(environment=environment)
    prompt_decision = policy_check(
        EntitlementAction.PROMPT_INCLUSION, classification, entitlement, context
    )
    if not prompt_decision.allowed:
        return prompt_decision
    return policy_check(EntitlementAction.SEND_TO_LLM, classification, entitlement, context)
