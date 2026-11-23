"""Integration test for FX Treasury daily fact build (offline fixtures)."""
from config.fx_treasury_thresholds import load_fx_treasury_thresholds
from src.silver.fx_treasury.build_features import build_daily_rows
from src.gold.fx_treasury_fact import build_fx_treasury_fact


def test_fx_treasury_daily_build_idempotent_shape():
    cfg = load_fx_treasury_thresholds()
    fx_rows = [{"as_of_date": "2024-01-01", "country": "ARG", "currency": "ARS", "fx_official": 1000.0, "fx_parallel": 1200.0, "fx_gap_pct": 20.0, "fx_vol_30d": 0.04}]
    stable_rows = [{"as_of_date": "2024-01-01", "asset": "USDC", "chain": "ethereum", "stablecoin_supply_usd": 1000.0, "stablecoin_supply_prev_usd": 1100.0}]
    yield_rows = [{"as_of_date": "2024-01-01", "asset": "USDC", "chain": "ethereum", "stablecoin_apy": 3.0}]
    macro_rows = [{"country": "ARG", "indicator": "reserves_usd", "value": 20000000000}, {"country": "ARG", "indicator": "gdp_usd", "value": 500000000000}, {"country": "ARG", "indicator": "external_debt_usd", "value": 200000000000}]
    news_rows = [{"country": "ARG", "tension_score": 0.8}]
    rows = build_daily_rows("2024-01-01", cfg, fx_rows, stable_rows, yield_rows, macro_rows, news_rows, tbill_rate=5.0)
    fact = build_fx_treasury_fact(rows, cfg)
    assert fact.height > 0
    assert "decision_action" in fact.columns
    arg = fact.filter((fact["country"] == "ARG") & (fact["asset"] == "USDC") & (fact["chain"] == "ethereum")).row(0, named=True)
    assert arg["alert_stablecoin_outflow"] is True
    assert arg["decision_action"] in {"REDUCE_EXPOSURE", "HEDGE_FX", "MOVE_TO_STABLECOIN", "MOVE_TO_TBILL", "HOLD_LOCAL"}
