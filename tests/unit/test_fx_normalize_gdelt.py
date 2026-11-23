"""Unit tests for GDELT normalization."""
from src.silver.fx_treasury.normalize_gdelt import normalize_gdelt_window


def test_normalize_gdelt_dedupe_and_tension():
    payload = {
        "country": "ARG",
        "window_start": "2024-01-01T00:00:00Z",
        "window_end": "2024-01-01T00:15:00Z",
        "query_hash": "abc",
        "articles": [
            {"url": "u1", "seendate": "20240101000100", "title": "Central bank devaluation", "tone": -5},
            {"url": "u1", "seendate": "20240101000100", "title": "Central bank devaluation", "tone": -5},
            {"url": "u2", "seendate": "20240101000200", "title": "Normal news", "tone": 1},
        ],
    }
    row = normalize_gdelt_window(payload, ["devaluation", "central bank"])
    assert row["article_count"] == 2
    assert row["negative_share"] == 0.5
    assert 0 <= row["tension_score"] <= 1
