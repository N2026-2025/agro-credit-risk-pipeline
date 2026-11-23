"""Feature assembly for FX Treasury Gold."""
from __future__ import annotations


def build_daily_rows(as_of_date: str, config: dict, fx_rows: list[dict], stable_rows: list[dict], yield_rows: list[dict], macro_rows: list[dict], news_rows: list[dict], tbill_rate: float | None) -> list[dict]:
    news_by_country = {r["country"]: r for r in news_rows}
    macro_by_country = {}
    for r in macro_rows:
        macro_by_country.setdefault(r["country"], []).append(r)
    fx_by_country = {r["country"]: r for r in fx_rows}
    yld = {(r["asset"], r["chain"]): r for r in yield_rows}
    st = {(r["asset"], r["chain"]): r for r in stable_rows}

    out = []
    for country in config.get("countries", []):
        ccode = country["code"]
        ccy = country.get("currency", "USD")
        fx = fx_by_country.get(ccode, {})
        news = news_by_country.get(ccode, {})
        macro = macro_by_country.get(ccode, [])
        reserves = next((m.get("value") for m in macro if m.get("indicator") == "reserves_usd"), None)
        prev_reserves = None
        for m in macro:
            if m.get("indicator") == "reserves_usd_prev":
                prev_reserves = m.get("value")
        reserves_change_pct = None
        if reserves is not None and prev_reserves not in (None, 0):
            reserves_change_pct = round(((reserves - prev_reserves) / prev_reserves) * 100, 4)
        sov_risk = None
        debt = next((m.get("value") for m in macro if m.get("indicator") == "external_debt_usd"), None)
        gdp = next((m.get("value") for m in macro if m.get("indicator") == "gdp_usd"), None)
        if debt is not None or reserves is not None:
            risk = 0.5
            if gdp and debt:
                risk += min(0.3, max(0.0, (debt / gdp) - 0.3) * 0.3)
            if gdp and reserves:
                risk -= min(0.2, (reserves / gdp) * 0.2)
            sov_risk = round(max(0.0, min(1.0, risk)), 4)

        for sc in config.get("stablecoins", []):
            asset = sc["symbol"]
            for chain in sc.get("chains", []):
                sr = st.get((asset, chain), {})
                yr = yld.get((asset, chain), {})
                supply = sr.get("stablecoin_supply_usd")
                prev_supply = sr.get("stablecoin_supply_prev_usd")
                flow_usd = None
                flow_pct = None
                if supply is not None and prev_supply is not None:
                    flow_usd = round(supply - prev_supply, 2)
                    if prev_supply != 0:
                        flow_pct = round((flow_usd / prev_supply) * 100, 4)
                apy = yr.get("stablecoin_apy")
                opportunity_spread_bps = None
                if apy is not None and tbill_rate is not None:
                    opportunity_spread_bps = round((float(apy) - float(tbill_rate)) * 100, 4)
                out.append({
                    "as_of_date": as_of_date,
                    "country": ccode,
                    "currency": ccy,
                    "asset": asset,
                    "chain": chain,
                    "fx_official": fx.get("fx_official"),
                    "fx_parallel": fx.get("fx_parallel"),
                    "fx_gap_pct": fx.get("fx_gap_pct"),
                    "fx_vol_30d": fx.get("fx_vol_30d"),
                    "stablecoin_supply_usd": supply,
                    "stablecoin_net_flow_usd": flow_usd,
                    "stablecoin_net_flow_pct": flow_pct,
                    "stablecoin_apy": apy,
                    "tbill_usd_rate": tbill_rate,
                    "local_rate": fx.get("local_rate"),
                    "opportunity_spread_bps": opportunity_spread_bps,
                    "sovereign_risk_score": sov_risk,
                    "reserves_change_pct": reserves_change_pct,
                    "news_tension_score": news.get("tension_score"),
                })
    return out
