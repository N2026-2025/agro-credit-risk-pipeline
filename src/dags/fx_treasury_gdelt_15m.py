"""Airflow DAG: fx_treasury_gdelt_15m."""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator

from config.fx_treasury_thresholds import load_fx_treasury_thresholds
from src.bronze.gdelt_news import extract_gdelt_15m
from src.silver.fx_treasury.normalize_gdelt import normalize_gdelt_window
from src.storage.fx_idempotent_writer import ensure_fx_tables, get_pg_conn, upsert_gdelt_15m


default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


def _window_end(context) -> datetime:
    # Airflow logical date is start of interval; for 15-min DAG use data interval end semantics when available
    logical = context.get("data_interval_end") or context.get("logical_date") or datetime.now(timezone.utc)
    if logical.tzinfo is None:
        logical = logical.replace(tzinfo=timezone.utc)
    return logical.astimezone(timezone.utc)


def _extract(**context):
    cfg = load_fx_treasury_thresholds()
    we = _window_end(context)
    countries = [c["code"] for c in cfg.get("countries", [])]
    keywords = cfg.get("gdelt", {}).get("keywords", [])
    max_records = int(cfg.get("gdelt", {}).get("max_records", 75))
    res = extract_gdelt_15m(we, countries, keywords, max_records=max_records)
    context["ti"].xcom_push(key="gdelt_raw", value=res)
    context["ti"].xcom_push(key="window_end", value=we.isoformat())


def _transform(**context):
    cfg = load_fx_treasury_thresholds()
    keywords = cfg.get("gdelt", {}).get("keywords", [])
    raw = context["ti"].xcom_pull(key="gdelt_raw", task_ids="extract_gdelt_15m") or {}
    rows = []
    for country, meta in raw.items():
        local = f"/tmp/gdelt_{country}_{datetime.fromisoformat(context['ti'].xcom_pull(key='window_end', task_ids='extract_gdelt_15m')).strftime('%Y%m%d%H%M')}.json"
        if not os.path.exists(local):
            # fallback: cannot read temp file in another worker; build minimal row
            rows.append({
                "country": country, "window_start": None, "window_end": context["ti"].xcom_pull(key="window_end", task_ids="extract_gdelt_15m"),
                "query_hash": meta.get("query_hash", hashlib.sha256(country.encode()).hexdigest()[:16]),
                "article_count": int(meta.get("count", 0)), "avg_tone": None, "negative_share": 0.0,
                "tension_score": min(1.0, int(meta.get("count", 0)) / 50.0), "top_keywords": keywords[:5], "raw_object_key": meta.get("key")
            })
            continue
        payload = json.load(open(local, encoding="utf-8"))
        row = normalize_gdelt_window(payload, keywords)
        row["raw_object_key"] = meta.get("key")
        rows.append(row)
    context["ti"].xcom_push(key="gdelt_rows", value=rows)


def _load(**context):
    rows = context["ti"].xcom_pull(key="gdelt_rows", task_ids="transform_gdelt_15m") or []
    if not rows:
        return 0
    conn = get_pg_conn()
    try:
        ensure_fx_tables(conn)
        return upsert_gdelt_15m(conn, rows)
    finally:
        conn.close()


with DAG(
    dag_id="fx_treasury_gdelt_15m",
    default_args=default_args,
    description="15-min GDELT news/tension ingestion for FX Treasury",
    schedule="*/15 * * * *",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
) as dag:
    extract = PythonOperator(task_id="extract_gdelt_15m", python_callable=_extract)
    transform = PythonOperator(task_id="transform_gdelt_15m", python_callable=_transform)
    load = PythonOperator(task_id="upsert_gdelt_15m", python_callable=_load)
    extract >> transform >> load
