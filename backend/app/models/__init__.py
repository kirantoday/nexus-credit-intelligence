"""Import every ORM model module so `Base.metadata` is always fully populated.

SQLAlchemy models register themselves into `Base.metadata` only when their
module is actually imported; foreign keys are resolved lazily, by string, on
first use. Without this, importing a single model module in isolation (e.g.
`app.models.financial_fact`, which references `provenance.id` and
`issuer.id` only as strings) can fail with `NoReferencedTableError` if
whatever else needed to import `app.models.provenance` never happened to run
first — a real bug caught in Milestone 3, not just a test artifact: the same
failure mode was reachable from any production code path that touched one
model without every other model already having been imported. Importing this
package (which any `from app.models.x import Y` does implicitly) now always
imports every model first, so `Base.metadata` is complete before any FK
resolves, regardless of import order.
"""

from __future__ import annotations

from app.models import (  # noqa: F401
    capital_structure,
    entitlement,
    financial_fact,
    fred,
    issuer,
    provenance,
    raw_provider_payload,
    security,
)
