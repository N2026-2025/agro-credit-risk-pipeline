"""Unit tests for DeFiLlama normalization."""
from src.silver.fx_treasury.normalize_defillama import normalize_stablecoin_rows, normalize_yield_rows


def test_normalize_stablecoin_rows_filters_configured_assets():
    raw = {"peggedAssets": [{"symbol": "USDC", "circulating": {"peggedUSD": {"ethereum": 1000}}, "circulatingPrevDay": {"peggedUSD": {"ethereum": 900}}}, {"symbol": "FOO", "circulating": {"peggedUSD": {"ethereum": 1}}}]}
    cfg = [{"symbol": "USDC", "chains": ["ethereum"]}]
    rows = normalize_stablecoin_rows(raw, "2024-01-01", cfg)
    assert len(rows) == 1
    assert rows[0]["asset"] == "USDC"
    assert rows[0]["stablecoin_supply_usd"] == 1000


def test_normalize_yield_rows_aggregates_best_apy():
    raw = {"data": [
        {"symbol": "USDC", "chain": "Ethereum", "project": "a", "apy": 5.0, "tvlUsd": 100},
        {"symbol": "USDC", "chain": "Ethereum", "project": "b", "apy": 7.0, "tvlUsd": 50},
    ]}
    cfg = [{"symbol": "USDC", "chains": ["ethereum"]}]
    rows = normalize_yield_rows(raw, "2024-01-01", cfg)
    assert len(rows) == 1
    assert rows[0]["stablecoin_apy"] == 7.0
