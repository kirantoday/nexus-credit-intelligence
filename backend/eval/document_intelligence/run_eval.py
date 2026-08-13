"""Document Intelligence deterministic eval runner (Milestone 10C).

    python -m eval.document_intelligence.run_eval

Extracts + chunks every fixture in `corpus_manifest.json` with the real
production pipeline and asserts each fixture's expectations. Writes a
plain JSON result file to `eval/document_intelligence/results/latest.json`
(gitignored — a run artifact, not version-controlled corpus content) with
one record per assertion: `assertion_type`, `expected`, `actual`,
`passed`, `fixture_id`, `extractor_version`, `chunking_strategy_version`.
Exits non-zero if any assertion failed — usable as a CI-style gate later,
even though nothing wires it into CI in 10C.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.extraction.chunker import CHUNKING_STRATEGY_VERSION, chunk_extraction
from app.extraction.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from app.extraction.validation import detect_needs_ocr

_BASE_DIR = Path(__file__).parent
_MANIFEST_PATH = _BASE_DIR / "corpus_manifest.json"
_RESULTS_PATH = _BASE_DIR / "results" / "latest.json"


@dataclass(frozen=True, slots=True)
class AssertionResult:
    fixture_id: str
    assertion_type: str
    expected: Any
    actual: Any
    passed: bool
    extractor_version: str
    chunking_strategy_version: str


def _assert(
    results: list[AssertionResult],
    *,
    fixture_id: str,
    assertion_type: str,
    expected: Any,
    actual: Any,
    extractor_version: str,
) -> None:
    results.append(
        AssertionResult(
            fixture_id=fixture_id,
            assertion_type=assertion_type,
            expected=expected,
            actual=actual,
            passed=(expected == actual) if not isinstance(expected, bool) else expected is actual,
            extractor_version=extractor_version,
            chunking_strategy_version=CHUNKING_STRATEGY_VERSION,
        )
    )


def _assert_true(
    results: list[AssertionResult],
    *,
    fixture_id: str,
    assertion_type: str,
    condition: bool,
    detail: Any,
    extractor_version: str,
) -> None:
    results.append(
        AssertionResult(
            fixture_id=fixture_id,
            assertion_type=assertion_type,
            expected=True,
            actual=detail,
            passed=condition,
            extractor_version=extractor_version,
            chunking_strategy_version=CHUNKING_STRATEGY_VERSION,
        )
    )


def run() -> list[AssertionResult]:
    manifest = json.loads(_MANIFEST_PATH.read_text())
    extractor = PyMuPDF4LLMExtractor()
    results: list[AssertionResult] = []

    for fixture in manifest["fixtures"]:
        fixture_id = fixture["id"]
        pdf_path = _BASE_DIR / fixture["file"]
        content = pdf_path.read_bytes()
        extraction = extractor.extract(content, content_type="application/pdf")
        needs_ocr = detect_needs_ocr(extraction)
        chunks = [] if needs_ocr else chunk_extraction(extraction)
        version = extraction.extractor_version

        _assert(
            results,
            fixture_id=fixture_id,
            assertion_type="page_count",
            expected=fixture["expected_page_count"],
            actual=extraction.page_count,
            extractor_version=version,
        )
        _assert(
            results,
            fixture_id=fixture_id,
            assertion_type="needs_ocr",
            expected=fixture["expected_needs_ocr"],
            actual=needs_ocr,
            extractor_version=version,
        )
        _assert_true(
            results,
            fixture_id=fixture_id,
            assertion_type="min_chunks",
            condition=len(chunks) >= fixture["expected_min_chunks"],
            detail={"expected_min": fixture["expected_min_chunks"], "actual": len(chunks)},
            extractor_version=version,
        )

        all_content = "\n".join(c.content for c in chunks)
        for heading in fixture["expected_headings_present"]:
            _assert_true(
                results,
                fixture_id=fixture_id,
                assertion_type="heading_present",
                condition=heading in all_content,
                detail=heading,
                extractor_version=version,
            )

        table_count = sum(1 for c in chunks if c.element_type.value == "table")
        _assert(
            results,
            fixture_id=fixture_id,
            assertion_type="table_count",
            expected=fixture["expected_table_count"],
            actual=table_count,
            extractor_version=version,
        )
        for expected_cell in fixture.get("expected_table_contains", []):
            table_content = "\n".join(c.content for c in chunks if c.element_type.value == "table")
            _assert_true(
                results,
                fixture_id=fixture_id,
                assertion_type="table_contains",
                condition=expected_cell in table_content,
                detail=expected_cell,
                extractor_version=version,
            )

        if fixture.get("expected_list_chunk_present"):
            _assert_true(
                results,
                fixture_id=fixture_id,
                assertion_type="list_chunk_present",
                condition=any(c.element_type.value == "list" for c in chunks),
                detail="at least one element_type=list chunk",
                extractor_version=version,
            )

        for entry in fixture["phrase_to_page"]:
            matching = [c for c in chunks if entry["phrase"] in c.content]
            actual_page = matching[0].page_start if matching else None
            _assert(
                results,
                fixture_id=fixture_id,
                assertion_type="phrase_to_page",
                expected={"phrase": entry["phrase"], "page": entry["expected_page"]},
                actual={"phrase": entry["phrase"], "page": actual_page},
                extractor_version=version,
            )

    return results


def main() -> int:
    results = run()
    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(json.dumps([asdict(r) for r in results], indent=2, default=str))

    failed = [r for r in results if not r.passed]
    print(f"=== Document Intelligence eval: {len(results)} assertions, {len(failed)} failed ===")
    for r in failed:
        print(
            f"  FAIL [{r.fixture_id}] {r.assertion_type}: expected={r.expected} actual={r.actual}"
        )
    print(f"Results written to {_RESULTS_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
