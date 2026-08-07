"""Unit test for `SecFullTextSearchResponseDTO` parsing (PLAN.md Milestone
7.5). Fixture below is a trimmed, real response captured live from
`efts.sec.gov/LATEST/search-index` (a `"chapter 11"` 8-K query,
2026-07-01..2026-07-02) before this DTO was implemented — not a guessed
shape. No network access in this test.
"""

from __future__ import annotations

import json

from app.providers.sec_edgar.dto import SecFullTextSearchResponseDTO

_REAL_CAPTURED_RESPONSE = """
{
  "hits": {
    "total": {"value": 3, "relation": "eq"},
    "hits": [
      {
        "_id": "0001193125-26-292501:d113173d8k.htm",
        "_source": {
          "ciks": ["0001001233"],
          "period_ending": "2026-06-24",
          "file_num": ["000-30171"],
          "display_names": ["SANGAMO THERAPEUTICS, INC  (SGMO)  (CIK 0001001233)"],
          "root_forms": ["8-K"],
          "file_date": "2026-07-01",
          "form": "8-K",
          "adsh": "0001193125-26-292501",
          "film_num": ["261145032"],
          "file_type": "8-K",
          "file_description": "8-K",
          "items": ["4.01", "8.01", "9.01"]
        }
      },
      {
        "_id": "0002031750-26-000052:ex101.htm",
        "_source": {
          "ciks": ["0002031750"],
          "display_names": ["Ares Core Infrastructure Fund  (CIK 0002031750)"],
          "root_forms": ["8-K"],
          "file_date": "2026-07-02",
          "form": "8-K",
          "adsh": "0002031750-26-000052",
          "file_type": "EX-10.1",
          "file_description": "EX-10.1",
          "items": ["1.01", "2.03", "9.01"]
        }
      }
    ]
  }
}
"""


def test_parses_real_captured_full_text_search_response() -> None:
    dto = SecFullTextSearchResponseDTO.model_validate(json.loads(_REAL_CAPTURED_RESPONSE))

    assert dto.hits.total.value == 3
    assert len(dto.hits.hits) == 2

    first = dto.hits.hits[0]
    assert first.id == "0001193125-26-292501:d113173d8k.htm"
    assert first.source.ciks == ["0001001233"]
    assert first.source.adsh == "0001193125-26-292501"
    assert first.source.form == "8-K"
    assert first.source.file_date == "2026-07-01"
    assert first.source.items == ["4.01", "8.01", "9.01"]
    assert "SANGAMO" in first.source.display_names[0]


def test_tolerates_hits_with_no_items_field() -> None:
    """A non-8-K filing's `_source` genuinely has no `items` field in real
    SEC responses — the DTO must default to an empty list, not error."""
    payload = {
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "hits": [
                {
                    "_id": "0001-1:doc.htm",
                    "_source": {
                        "ciks": ["0000320193"],
                        "display_names": ["APPLE INC (CIK 0000320193)"],
                        "root_forms": ["10-K"],
                        "file_date": "2026-07-01",
                        "form": "10-K",
                        "adsh": "0001-26-000001",
                    },
                }
            ],
        }
    }

    dto = SecFullTextSearchResponseDTO.model_validate(payload)

    assert dto.hits.hits[0].source.items == []
