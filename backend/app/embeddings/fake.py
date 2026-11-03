"""Deterministic fake `EmbeddingProvider` (Milestone 10D.2) — the only
implementation in this milestone, and the only one tests may use.

Vectors are derived from SHA-256 of (input type, text), so the same input
always yields the same unit-length vector, different text yields a
different vector, and a document embedding of a string differs from a query
embedding of the same string (mirroring vendors with asymmetric task
types). No network, no randomness, no clock.

Failure injection (`fail_next`) and call recording (`calls`) exist for
tests. Recorded calls keep the received texts because this is a test
double; production code never logs them.
"""

from __future__ import annotations

import hashlib
import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.core.types import EmbeddingInputType
from app.embeddings.base import EmbeddingResult
from app.embeddings.errors import EmbeddingInputError
from app.embeddings.fingerprint import estimate_tokens

FAKE_PROVIDER_NAME = "fake"
FAKE_MODEL_ID = "fake-embedding"
FAKE_MODEL_VERSION = "fake-1"


@dataclass(slots=True)
class FakeCall:
    input_type: EmbeddingInputType
    texts: list[str]


@dataclass(slots=True)
class FakeEmbeddingProvider:
    dimension: int = 1024
    model_id: str = FAKE_MODEL_ID
    model_version: str = FAKE_MODEL_VERSION
    max_batch_size: int = 64
    report_usage: bool = True
    max_input_chars: int | None = None
    calls: list[FakeCall] = field(default_factory=list)
    _failures: deque[BaseException] = field(default_factory=deque)
    _scheduled_failures: dict[int, BaseException] = field(default_factory=dict)
    # Test hooks to simulate a misbehaving vendor.
    returned_dimension: int | None = None
    returned_model_version: str | None = None
    drop_last_vector: bool = False

    provider_name: str = FAKE_PROVIDER_NAME

    def fail_next(self, error: BaseException, *, times: int = 1) -> None:
        for _ in range(times):
            self._failures.append(error)

    def fail_on_call(self, call_number: int, error: BaseException) -> None:
        """Fails the `call_number`-th call (1-based, counting every call
        made on this instance) and no other."""
        self._scheduled_failures[call_number] = error

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def texts_sent(self) -> int:
        return sum(len(call.texts) for call in self.calls)

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingResult:
        return self._embed(list(texts), EmbeddingInputType.DOCUMENT)

    def embed_query(self, text: str) -> EmbeddingResult:
        return self._embed([text], EmbeddingInputType.QUERY)

    def _embed(self, texts: list[str], input_type: EmbeddingInputType) -> EmbeddingResult:
        self.calls.append(FakeCall(input_type=input_type, texts=texts))
        scheduled = self._scheduled_failures.pop(len(self.calls), None)
        if scheduled is not None:
            raise scheduled
        if self._failures:
            raise self._failures.popleft()
        if len(texts) > self.max_batch_size:
            raise EmbeddingInputError(f"batch of {len(texts)} exceeds max {self.max_batch_size}")
        if self.max_input_chars is not None and any(len(t) > self.max_input_chars for t in texts):
            raise EmbeddingInputError("an input exceeds the maximum input length")

        vectors = [_vector_for(t, input_type, self.dimension) for t in texts]
        if self.drop_last_vector and vectors:
            vectors = vectors[:-1]
        return EmbeddingResult(
            vectors=vectors,
            model_id=self.model_id,
            model_version=self.returned_model_version or self.model_version,
            dimension=self.returned_dimension or self.dimension,
            input_tokens=sum(estimate_tokens(t) for t in texts) if self.report_usage else None,
        )


def _vector_for(text: str, input_type: EmbeddingInputType, dimension: int) -> list[float]:
    seed = hashlib.sha256(f"{input_type.value}\x00{text}".encode()).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        values.extend((b - 127.5) / 127.5 for b in block)
        counter += 1
    values = values[:dimension]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]
