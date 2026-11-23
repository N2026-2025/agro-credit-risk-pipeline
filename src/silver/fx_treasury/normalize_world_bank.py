"""Silver normalization for World Bank indicators."""
from __future__ import annotations


def latest_non_null(rows: list[dict]) -> dict | None:
    for r in rows:
        val = r.get("value")
        if val is not None:
            return r
    return None


def normalize_world_bank(raw_country: dict, eval_date: str) -> list[dict]:
    country = raw_country.get("country")
    out = []
    for ind in raw_country.get("indicators", []):
        name = ind.get("indicator_name")
        rows = ind.get("rows", []) or []
        last = latest_non_null(rows)
        out.append({
            "as_of_date": eval_date,
            "country": country,
            "indicator": name,
            "value": float(last["value"]) if last and last.get("value") is not None else None,
            "period": last.get("date") if last else None,
        })
    return out


def compute_sovereign_risk(indicator_rows: list[dict]) -> float | None:
    # simple bounded proxy: lower reserves and higher external debt => higher risk
    vals = {r["indicator"]: r.get("value") for r in indicator_rows}
    reserves = vals.get("reserves_usd")
    debt = vals.get("external_debt_usd")
    gdp = vals.get("gdp_usd")
    if reserves is None and debt is None:
        return None
    risk = 0.5
    if gdp and debt:
        risk += min(0.3, max(0.0, (debt / gdp) - 0.3) * 0.3)
    if gdp and reserves:
        risk -= min(0.2, (reserves / gdp) * 0.2)
    return round(max(0.0, min(1.0, risk)), 4)
