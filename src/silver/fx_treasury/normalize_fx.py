"""Silver normalization for FX/rates and feature building."""
from __future__ import annotations


def compute_gap_pct(official: float | None, parallel: float | None) -> float | None:
    if official in (None, 0) or parallel is None:
        return None
    return round(((parallel - official) / official) * 100, 4)


def compute_volatility(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return round(var ** 0.5, 6)


def build_fx_features(as_of_date: str, country: str, currency: str, official: float | None, parallel: float | None, history: list[float] | None = None) -> dict:
    history = history or []
    return {
        "as_of_date": as_of_date,
        "country": country,
        "currency": currency,
        "fx_official": official,
        "fx_parallel": parallel,
        "fx_gap_pct": compute_gap_pct(official, parallel),
        "fx_vol_30d": compute_volatility(history),
    }
