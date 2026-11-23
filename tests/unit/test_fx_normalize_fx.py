"""Unit tests for FX normalization."""
from src.silver.fx_treasury.normalize_fx import compute_gap_pct, compute_volatility, build_fx_features


def test_compute_gap_pct():
    assert compute_gap_pct(100, 120) == 20.0
    assert compute_gap_pct(0, 120) is None


def test_compute_volatility():
    vol = compute_volatility([100, 101, 99, 102])
    assert vol is not None and vol > 0


def test_build_fx_features():
    row = build_fx_features("2024-01-01", "ARG", "ARS", 1000.0, 1200.0, [1000, 1100, 1200])
    assert row["fx_gap_pct"] == 20.0
    assert row["country"] == "ARG"
