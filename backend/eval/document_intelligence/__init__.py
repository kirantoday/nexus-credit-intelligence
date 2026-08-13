"""Document Intelligence deterministic evaluation corpus (Milestone 10C).

`corpus_manifest.yaml` is the version-controlled source of truth for
expected structural facts (page counts, headings, table presence,
citation locations) about each fixture in `fixtures/`. `run_eval.py`
extracts + chunks every fixture with the real production pipeline
(`app.extraction.pymupdf4llm_extractor`/`app.extraction.chunker`) and
asserts against the manifest, writing a plain, vendor-neutral JSON result
file — never a database table (explicitly deferred to 10D+, once
retrieval evaluation needs to track results across runs). No Ragas, no
LLM-as-judge — every assertion here is deterministic.
"""

from __future__ import annotations
