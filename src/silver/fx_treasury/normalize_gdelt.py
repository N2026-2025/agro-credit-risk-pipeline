"""Silver normalization for GDELT 15-min windows."""
from __future__ import annotations

import hashlib


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def normalize_gdelt_window(payload: dict, keywords: list[str]) -> dict:
    articles = payload.get("articles", []) or []
    seen = set()
    tones = []
    negative = 0
    hits = 0
    for a in articles:
        url = a.get("url") or ""
        seendate = a.get("seendate") or ""
        key = hashlib.sha256(f"{url}|{seendate}".encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        tone = _safe_float(a.get("tone"))
        if tone is not None:
            tones.append(tone)
            if tone < 0:
                negative += 1
        title = (a.get("title") or "").lower()
        if any(k.lower() in title for k in keywords):
            hits += 1
    count = len(seen)
    avg_tone = sum(tones) / len(tones) if tones else None
    negative_share = (negative / len(tones)) if tones else 0.0
    # tension score: combine negative share, volume, and keyword hits (bounded 0-1)
    vol_component = min(1.0, count / 50.0)
    neg_component = min(1.0, negative_share)
    hit_component = min(1.0, hits / max(1, count))
    tension = (0.5 * neg_component) + (0.3 * vol_component) + (0.2 * hit_component)
    return {
        "country": payload.get("country"),
        "window_start": payload.get("window_start"),
        "window_end": payload.get("window_end"),
        "query_hash": payload.get("query_hash"),
        "article_count": count,
        "avg_tone": round(avg_tone, 4) if avg_tone is not None else None,
        "negative_share": round(negative_share, 4),
        "tension_score": round(max(0.0, min(1.0, tension)), 4),
        "top_keywords": keywords[:5],
    }
