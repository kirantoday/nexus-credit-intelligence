"""Document Intelligence tracing (Milestone 10C).

**Correlation-ID decision** (see the milestone brief's explicit
instruction to challenge persisting trace context before doing it):
`document_extraction.id` — already a stable, already-persisted UUID — is
the durable cross-process correlation identifier, attached as the
`extraction_id` attribute on every span this module creates, in every
process. A persisted W3C `traceparent` column was considered and
deliberately **not** added: true unbroken trace-parent continuity across
the enqueue-request/worker-claim process boundary only has value once a
real trace backend exists to visualize it, and 10C wires no exporter at
all (see the module docstring on why — no observability vendor in this
milestone). Each process (the enqueue request, each worker invocation)
therefore starts its own root span; correlating them today means
filtering on `extraction_id`, which every span already carries. Revisit
persisting `traceparent` only when a real backend is chosen and continuous
cross-process traces are worth the schema cost — not speculatively now.

**Exporter**: none, by default — spans are created via the OTel API but
dropped by the default no-op processor unless `OTEL_CONSOLE_EXPORT=true`
is set, which wires the OTel SDK's own built-in `ConsoleSpanExporter`
(part of `opentelemetry-sdk` itself — not a vendor/platform dependency,
just stdout) for local development visibility. No Datadog/Honeycomb/Azure
Monitor/Google-specific exporter exists anywhere in this codebase.

**Never put document/chunk text on a span** — every helper below takes
only the specific scalar attributes listed in the milestone brief
(extraction id, source type, extractor/version, chunker version, counts,
duration, retry count, status, error classification), never a `content`/
`text` parameter, so there is no code path by which extracted document
text could reach telemetry.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from uuid import UUID

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

_TRACER_NAME = "nexus.document_intelligence"


@lru_cache
def _configure_provider() -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create({"service.name": "nexus-document-intelligence"})
    )
    if os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return provider


def get_tracer() -> trace.Tracer:
    _configure_provider()
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def document_intelligence_span(
    name: str, *, extraction_id: UUID | None, **attributes: Any
) -> Iterator[trace.Span]:
    """`name` should be one of the eight documented pipeline boundaries
    (`document_intelligence.enqueue`, `.worker_claim`, `.storage_download`,
    `.extract`, `.chunk`, `.validate`, `.persist`, `.promote`).
    `extraction_id` is the correlation field every span in this pipeline
    carries — `None` only for `.worker_claim`'s "did anything exist to
    claim at all" moment, before a row id is known; the caller sets it via
    `span.set_attribute("extraction_id", ...)` once the claim resolves.
    Sets the span status to ERROR (with the exception's type name, never
    its full text/args, which could echo user-controlled input) and
    re-raises on any exception."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if extraction_id is not None:
            span.set_attribute("extraction_id", str(extraction_id))
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise
