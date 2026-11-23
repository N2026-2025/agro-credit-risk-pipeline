"""Silver normalization for DeFiLlama stablecoins/yields."""
from __future__ import annotations


def normalize_stablecoin_rows(raw: dict, eval_date: str, configured: list[dict]) -> list[dict]:
    assets = {a.get("symbol", "").upper() for a in configured}
    chain_map = {a.get("symbol", "").upper(): [c.lower() for c in a.get("chains", [])] for a in configured}
    rows = []
    for item in raw.get("peggedAssets", []):
        symbol = str(item.get("symbol", "")).upper()
        if symbol not in assets:
            continue
        circulating = item.get("circulating", {}) or {}
        prev = item.get("circulatingPrevDay", {}) or item.get("circulatingPrevWeek", {}) or {}
        by_chain = circulating.get("peggedUSD", None)
        if isinstance(by_chain, dict):
            for chain, value in by_chain.items():
                chain_l = str(chain).lower()
                if chain_l not in chain_map.get(symbol, []):
                    continue
                prev_val = None
                if isinstance(prev.get("peggedUSD"), dict):
                    prev_val = prev["peggedUSD"].get(chain)
                rows.append({
                    "as_of_date": eval_date,
                    "asset": symbol,
                    "chain": chain_l,
                    "stablecoin_supply_usd": float(value) if value is not None else None,
                    "stablecoin_supply_prev_usd": float(prev_val) if prev_val is not None else None,
                })
        else:
            total = circulating.get("peggedUSD")
            prev_total = prev.get("peggedUSD") if isinstance(prev, dict) else None
            for chain_l in chain_map.get(symbol, []):
                rows.append({
                    "as_of_date": eval_date,
                    "asset": symbol,
                    "chain": chain_l,
                    "stablecoin_supply_usd": float(total) if isinstance(total, (int, float)) else None,
                    "stablecoin_supply_prev_usd": float(prev_total) if isinstance(prev_total, (int, float)) else None,
                })
    return rows


def normalize_yield_rows(raw: dict, eval_date: str, configured: list[dict]) -> list[dict]:
    assets = {a.get("symbol", "").upper() for a in configured}
    chain_map = {a.get("symbol", "").upper(): [c.lower() for c in a.get("chains", [])] for a in configured}
    rows = []
    for pool in raw.get("data", []):
        symbol = str(pool.get("symbol", "")).upper()
        chain = str(pool.get("chain", "")).lower()
        # symbol may be composite like USDC-USDT; keep exact matches
        if symbol not in assets or chain not in chain_map.get(symbol, []):
            continue
        rows.append({
            "as_of_date": eval_date,
            "asset": symbol,
            "chain": chain,
            "project": pool.get("project"),
            "stablecoin_apy": float(pool.get("apy")) if pool.get("apy") is not None else None,
            "tvl_usd": float(pool.get("tvlUsd")) if pool.get("tvlUsd") is not None else None,
        })
    # aggregate best APY by asset-chain
    agg = {}
    for r in rows:
        k = (r["asset"], r["chain"])
        cur = agg.get(k)
        if cur is None or (r["stablecoin_apy"] or -1) > (cur["stablecoin_apy"] or -1):
            agg[k] = r
    return list(agg.values())
