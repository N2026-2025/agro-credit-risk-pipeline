"""Airflow DAG: fx_treasury_daily."""
import json
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from config.fx_treasury_thresholds import load_fx_treasury_thresholds
from src.bronze.defillama_stablecoins import extract_defillama_stablecoins
from src.bronze.defillama_yields import extract_defillama_yields
from src.bronze.world_bank import extract_world_bank
from src.bronze.fred_fx import extract_fred
from src.bronze.bcra_fx import extract_bcra_fx
from src.silver.fx_treasury.normalize_defillama import normalize_stablecoin_rows, normalize_yield_rows
from src.silver.fx_treasury.normalize_world_bank import normalize_world_bank
from src.silver.fx_treasury.normalize_fx import build_fx_features
from src.silver.fx_treasury.build_features import build_daily_rows
from src.gold.fx_treasury_fact import build_fx_treasury_fact
from src.storage.fx_idempotent_writer import ensure_fx_tables, get_pg_conn, upsert_fx_treasury_daily


default_args = {"owner": "data-eng", "depends_on_past": False, "retries": 2, "retry_delay": timedelta(minutes=5)}


def _eval_date(context):
    return context["ds"]


def _extract_defillama_stablecoins(**context):
    res = extract_defillama_stablecoins(_eval_date(context))
    context["ti"].xcom_push(key="defillama_stablecoins", value=res)


def _extract_defillama_yields(**context):
    res = extract_defillama_yields(_eval_date(context))
    context["ti"].xcom_push(key="defillama_yields", value=res)


def _extract_world_bank(**context):
    cfg = load_fx_treasury_thresholds()
    countries = [c["code"] for c in cfg.get("countries", [])]
    indicators = cfg.get("world_bank_indicators", {})
    res = extract_world_bank(_eval_date(context), countries, indicators)
    context["ti"].xcom_push(key="world_bank", value=res)


def _extract_fred(**context):
    cfg = load_fx_treasury_thresholds()
    res = extract_fred(_eval_date(context), cfg.get("fred_series", {}), os.getenv("FRED_API_KEY"))
    context["ti"].xcom_push(key="fred", value=res)


def _extract_bcra_fx(**context):
    res = extract_bcra_fx(_eval_date(context))
    context["ti"].xcom_push(key="bcra_fx", value=res)


def _load_json_local(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_and_load(**context):
    cfg = load_fx_treasury_thresholds()
    eval_date = _eval_date(context)
    stable_raw = _load_json_local(f"/tmp/defillama_stablecoins_{eval_date}.json")
    yields_raw = _load_json_local(f"/tmp/defillama_yields_{eval_date}.json")
    stable_rows = normalize_stablecoin_rows(stable_raw, eval_date, cfg.get("stablecoins", []))
    yield_rows = normalize_yield_rows(yields_raw, eval_date, cfg.get("stablecoins", []))

    macro_rows = []
    for c in cfg.get("countries", []):
        payload = _load_json_local(f"/tmp/world_bank_{c['code']}_{eval_date}.json")
        if payload:
            macro_rows.extend(normalize_world_bank(payload, eval_date))

    # FX features: minimal MVP defaults; can be replaced with FRED/BCRA normalized series
    fx_rows = []
    for c in cfg.get("countries", []):
        official = 1.0 if c["currency"] == "USD" else None
        parallel = official
        fx_rows.append(build_fx_features(eval_date, c["code"], c["currency"], official, parallel, history=[]))
    # basic ARS sample from thresholds/assumptions if not present
    for r in fx_rows:
        if r["country"] == "ARG" and r.get("fx_official") is None:
            r["fx_official"] = 1000.0
            r["fx_parallel"] = 1200.0
            r["fx_gap_pct"] = 20.0
            r["fx_vol_30d"] = 0.04

    # GDELT daily snapshot: aggregate from 15m fact table when available, else empty
    news_rows = []
    conn = get_pg_conn()
    try:
        ensure_fx_tables(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT country, AVG(tension_score), AVG(avg_tone), SUM(article_count)
                FROM fact_gdelt_tension_15m
                WHERE window_start::date = %s::date
                GROUP BY country
            """, (eval_date,))
            for country, tension, tone, count in cur.fetchall():
                news_rows.append({"country": country, "tension_score": float(tension) if tension is not None else None, "avg_tone": float(tone) if tone is not None else None, "article_count": int(count or 0)})

        tbill_rate = None
        tbill_payload = _load_json_local(f"/tmp/fred_{cfg.get('fred_series',{}).get('tbill_3m','DTB3')}_{eval_date}.json")
        obs = tbill_payload.get("observations", [])
        for o in reversed(obs):
            v = o.get("value")
            if v not in (None, "."):
                try:
                    tbill_rate = float(v)
                    break
                except Exception:
                    pass

        rows = build_daily_rows(eval_date, cfg, fx_rows, stable_rows, yield_rows, macro_rows, news_rows, tbill_rate)
        fact = build_fx_treasury_fact(rows, cfg)
        n = upsert_fx_treasury_daily(conn, fact.to_dicts())
        return n
    finally:
        conn.close()


with DAG(
    dag_id="fx_treasury_daily",
    default_args=default_args,
    description="Daily FX & Treasury risk pipeline: DeFiLlama + World Bank + GDELT snapshot + FRED/BCRA + Gold",
    schedule="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
) as dag:
    t1 = PythonOperator(task_id="extract_defillama_stablecoins", python_callable=_extract_defillama_stablecoins)
    t2 = PythonOperator(task_id="extract_defillama_yields", python_callable=_extract_defillama_yields)
    t3 = PythonOperator(task_id="extract_world_bank", python_callable=_extract_world_bank)
    t4 = PythonOperator(task_id="extract_fred", python_callable=_extract_fred)
    t5 = PythonOperator(task_id="extract_bcra_fx", python_callable=_extract_bcra_fx)
    t6 = PythonOperator(task_id="build_and_load_fx_treasury_fact", python_callable=_build_and_load)

    [t1, t2, t3, t4, t5] >> t6
