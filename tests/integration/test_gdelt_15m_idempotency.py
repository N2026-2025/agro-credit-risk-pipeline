"""Integration-style test for GDELT 15m idempotent key behavior."""
from src.silver.fx_treasury.normalize_gdelt import normalize_gdelt_window


def test_gdelt_window_idempotent_key_fields():
    payload = {
        "country": "ARG", "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T00:15:00Z",
        "query_hash": "samehash",
        "articles": [{"url": "a", "seendate": "1", "title": "devaluation", "tone": -2}],
    }
    r1 = normalize_gdelt_window(payload, ["devaluation"])
    r2 = normalize_gdelt_window(payload, ["devaluation"])
    assert r1["country"] == r2["country"]
    assert r1["window_start"] == r2["window_start"]
    assert r1["query_hash"] == r2["query_hash"]
    assert r1["article_count"] == r2["article_count"]
