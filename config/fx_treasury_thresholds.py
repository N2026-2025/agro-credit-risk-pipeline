"""Configuration loader for FX Treasury thresholds."""
from pathlib import Path


DEFAULTS = {
    "countries": [
        {"code": "ARG", "name": "Argentina", "currency": "ARS", "role": "base"},
        {"code": "BRA", "name": "Brazil", "currency": "BRL", "role": "trade_partner"},
        {"code": "CHN", "name": "China", "currency": "CNY", "role": "trade_partner"},
        {"code": "USA", "name": "United States", "currency": "USD", "role": "trade_partner"},
        {"code": "DEU", "name": "Germany", "currency": "EUR", "role": "trade_partner"},
        {"code": "ESP", "name": "Spain", "currency": "EUR", "role": "trade_partner"},
        {"code": "CHL", "name": "Chile", "currency": "CLP", "role": "trade_partner"},
        {"code": "PRY", "name": "Paraguay", "currency": "PYG", "role": "trade_partner"},
        {"code": "URY", "name": "Uruguay", "currency": "UYU", "role": "trade_partner"},
        {"code": "MEX", "name": "Mexico", "currency": "MXN", "role": "trade_partner"},
        {"code": "BOL", "name": "Bolivia", "currency": "BOB", "role": "trade_partner"},
    ],
    "stablecoins": [
        {"symbol": "USDC", "chains": ["ethereum", "polygon", "arbitrum"]},
        {"symbol": "USDT", "chains": ["ethereum", "tron", "polygon"]},
        {"symbol": "DAI", "chains": ["ethereum", "polygon", "arbitrum"]},
    ],
    "world_bank_indicators": {
        "reserves_usd": "FI.RES.TOTL.CD",
        "external_debt_usd": "DT.DOD.DECT.CD",
        "current_account_usd": "BN.CAB.XOKA.CD",
        "gdp_usd": "NY.GDP.MKTP.CD",
    },
    "fred_series": {"tbill_3m": "DTB3", "usd_index": "DTWEXBGS"},
    "gdelt": {
        "keywords": ["central bank", "devaluation", "interest rate", "capital controls", "currency controls", "default", "inflation"],
        "window_minutes": 15,
        "max_records": 75,
    },
    "alerts": {
        "fx_gap_pct_threshold": 20.0,
        "fx_vol_30d_threshold": 0.05,
        "stablecoin_outflow_pct_threshold": -2.0,
        "reserves_drop_pct_threshold": -5.0,
        "news_tension_threshold": 0.7,
        "yield_anomaly_bps_threshold": 300,
    },
    "decision_rules": {
        "version": "1.0",
        "reduce_exposure": {"news_tension_min": 0.7, "fx_gap_pct_min": 20.0, "stablecoin_net_flow_max": 0.0},
        "hedge_fx": {"fx_vol_30d_min": 0.05, "fx_gap_pct_min": 15.0},
        "move_to_stablecoin": {"opportunity_spread_bps_min": 150, "max_stablecoin_outflow_pct": -2.0, "sovereign_risk_max": 0.7},
        "move_to_tbill": {"tbill_over_stablecoin_apy_bps_min": 100, "policy_allows_tbill": True},
    },
    "freshness_sla_hours": {"defillama": 24, "world_bank": 8760, "gdelt": 1, "fred": 24, "bcra_fx": 24},
}


def load_fx_treasury_thresholds(path: str = "config/fx_treasury_thresholds.yml") -> dict:
    p = Path(path)
    cfg = {k: (v.copy() if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    if not p.exists():
        return cfg
    try:
        import yaml

        with open(p) as f:
            loaded = yaml.safe_load(f) or {}
        for k, v in loaded.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                merged = cfg[k].copy()
                merged.update(v)
                cfg[k] = merged
            else:
                cfg[k] = v
    except Exception:
        return cfg
    return cfg
