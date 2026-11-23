"""Unit tests for FX treasury fact alerts and formal decisions."""
from config.fx_treasury_thresholds import load_fx_treasury_thresholds
from src.gold.fx_treasury_fact import build_fx_treasury_fact


def base_row(**overrides):
    row = {
        "as_of_date": "2024-01-01", "country": "ARG", "currency": "ARS", "asset": "USDC", "chain": "ethereum",
        "fx_official": 1000.0, "fx_parallel": 1100.0, "fx_gap_pct": 10.0, "fx_vol_30d": 0.02,
        "stablecoin_supply_usd": 1000.0, "stablecoin_net_flow_usd": 10.0, "stablecoin_net_flow_pct": 1.0,
        "stablecoin_apy": 4.0, "tbill_usd_rate": 5.0, "local_rate": 30.0, "opportunity_spread_bps": -100.0,
        "sovereign_risk_score": 0.5, "reserves_change_pct": 0.5, "news_tension_score": 0.2,
    }
    row.update(overrides)
    return row


def test_reduce_exposure_rule():
    cfg = load_fx_treasury_thresholds()
    df = build_fx_treasury_fact([base_row(fx_gap_pct=25.0, news_tension_score=0.8, stablecoin_net_flow_usd=-100.0)], cfg)
    r = df.row(0, named=True)
    assert r["decision_action"] == "REDUCE_EXPOSURE"
    assert r["alert_fx_gap"] is True
    assert r["alert_news_tension"] is True


def test_move_to_tbill_rule():
    cfg = load_fx_treasury_thresholds()
    df = build_fx_treasury_fact([base_row(stablecoin_apy=2.0, tbill_usd_rate=4.0, opportunity_spread_bps=-200.0)], cfg)
    r = df.row(0, named=True)
    assert r["decision_action"] == "MOVE_TO_TBILL"


def test_default_hold_local():
    cfg = load_fx_treasury_thresholds()
    df = build_fx_treasury_fact([base_row(tbill_usd_rate=4.0, stablecoin_apy=4.1)], cfg)
    r = df.row(0, named=True)
    assert r["decision_action"] == "HOLD_LOCAL"
