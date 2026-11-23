"""Idempotent writers for FX Treasury fact tables."""
from __future__ import annotations

import json
import logging

import psycopg2

logger = logging.getLogger(__name__)


def get_pg_conn():
    import os
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        dbname=os.getenv("POSTGRES_DB", "agro"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def ensure_fx_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(open("sql/fx_treasury_schema.sql", encoding="utf-8").read())
    conn.commit()


def upsert_gdelt_15m(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = ["country","window_start","window_end","query_hash","article_count","avg_tone","negative_share","tension_score","top_keywords","raw_object_key","ingested_at"]
    values = []
    for r in rows:
        values.append(tuple(json.dumps(r.get(c)) if c == "top_keywords" else r.get(c) for c in cols))
    update = ", ".join([f"{c}=EXCLUDED.{c}" for c in cols if c not in ("country","window_start","query_hash")])
    with conn.cursor() as cur:
        from psycopg2.extras import execute_values
        execute_values(cur, f"INSERT INTO fact_gdelt_tension_15m ({','.join(cols)}) VALUES %s ON CONFLICT (country, window_start, query_hash) DO UPDATE SET {update}", values)
    conn.commit()
    return len(rows)


def upsert_fx_treasury_daily(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = [
        "as_of_date","country","currency","asset","chain","fx_official","fx_parallel","fx_gap_pct","fx_vol_30d",
        "stablecoin_supply_usd","stablecoin_net_flow_usd","stablecoin_net_flow_pct","stablecoin_apy","tbill_usd_rate",
        "local_rate","opportunity_spread_bps","sovereign_risk_score","reserves_change_pct","news_tension_score",
        "alert_fx_gap","alert_stablecoin_outflow","alert_reserves_drop","alert_news_tension","alert_yield_anomaly",
        "decision_action","decision_reason","decision_confidence","decision_rule_version","decision_inputs_json"
    ]
    values = []
    for r in rows:
        row_vals = []
        for c in cols:
            v = r.get(c)
            if c == "decision_inputs_json" and isinstance(v, str):
                row_vals.append(v)
            elif c == "decision_inputs_json":
                row_vals.append(json.dumps(v) if v is not None else None)
            else:
                row_vals.append(v)
        values.append(tuple(row_vals))
    update = ", ".join([f"{c}=EXCLUDED.{c}" for c in cols if c not in ("as_of_date","country","currency","asset","chain")]) + ", processed_at=NOW()"
    from psycopg2.extras import execute_values
    with conn.cursor() as cur:
        execute_values(cur, f"INSERT INTO fact_treasury_risk_daily ({','.join(cols)}) VALUES %s ON CONFLICT (as_of_date,country,currency,asset,chain) DO UPDATE SET {update}", values)
    conn.commit()
    return len(rows)
