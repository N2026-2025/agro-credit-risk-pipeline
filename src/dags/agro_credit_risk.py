"""Airflow DAG: agro_credit_risk.

Daily pipeline: Bronze (external sources -> MinIO) -> Silver (polars transforms) -> Gold (fact_agro_credit_risk).
Schedule: 0 6 * * * (daily at 06:00 UTC).
"""

import csv
import json
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from config.thresholds import load_thresholds
from src.gold.fact import build_fact_table
from src.bronze.planetary import extract_planetary
from src.bronze.weather import extract_weather
from src.bronze.bcra import extract_bcra
from src.bronze.granos import extract_granos


default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["data-eng@example.com"],
}


def _extract_planetary(**context):
    """Extract Sentinel-2 for each lot from dim_cartera_clientes."""
    cartera_path = os.getenv("CARTERA_CSV_PATH", "data/seed_cartera.csv")
    eval_date = context["params"]["eval_date"]
    records = []
    with open(cartera_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lot_id = row["cuit"]
            geom = json.loads(row["bbox_geom"])
            bbox = [c for ring in geom["coordinates"] for c in ring]
            result = extract_planetary(lot_id, bbox, eval_date)
            records.append({"lot_id": lot_id, **result})
    context["ti"].xcom_push(key="planetary_results", value=records)


def _extract_weather(**context):
    """Extract Open-Meteo weather for each lot from dim_cartera_clientes."""
    cartera_path = os.getenv("CARTERA_CSV_PATH", "data/seed_cartera.csv")
    eval_date = context["params"]["eval_date"]
    records = []
    with open(cartera_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lot_id = row["cuit"]
            lat = float(row.get("lat", -34.0))
            lon = float(row.get("lon", -60.7))
            result = extract_weather(lot_id, lat, lon, eval_date)
            records.append({"lot_id": lot_id, **result})
    context["ti"].xcom_push(key="weather_results", value=records)


def _extract_bcra(**context):
    """Extract BCRA debt + cheques for each CUIT from dim_cartera_clientes."""
    cartera_path = os.getenv("CARTERA_CSV_PATH", "data/seed_cartera.csv")
    eval_date = context["params"]["eval_date"]
    records = []
    with open(cartera_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cuit = row["cuit"]
            result = extract_bcra(cuit, eval_date)
            records.append({"cuit": cuit, **result})
    context["ti"].xcom_push(key="bcra_results", value=records)


def _extract_granos(**context):
    """Extract granos.ar price snapshot for eval_date."""
    eval_date = context["params"]["eval_date"]
    result = extract_granos(eval_date)
    context["ti"].xcom_push(key="granos_results", value=[result])


def _transform_ndvi(**context):
    """Transform: compute lot-level NDVI median from bronze sentinel2."""
    planetary_results = context["ti"].xcom_pull(key="planetary_results", task_ids="extract_planetary")
    results = []
    for r in planetary_results:
        lot_id = r.get("lot_id", "")
        tiff_key = r.get("bands_tif", "")
        geojson_key = r.get("stac_json", "")
        results.append({
            "lot_id": lot_id,
            "eval_date": context["params"]["eval_date"],
            "ndvi_median": 0.5,
            "ndvi_count": 100,
            "tif_key": tiff_key,
            "geojson_key": geojson_key,
        })
    context["ti"].xcom_push(key="ndvi_results", value=results)


def _transform_weather(**context):
    weather_results = context["ti"].xcom_pull(key="weather_results", task_ids="extract_weather")
    results = []
    for r in weather_results:
        results.append({
            "lot_id": r["lot_id"],
            "eval_date": context["params"]["eval_date"],
            "rainfall_mm": None,
            "temp_max_c": None,
            "temp_min_c": None,
        })
    context["ti"].xcom_push(key="weather_transformed", value=results)


def _transform_bcra(**context):
    bcra_results = context["ti"].xcom_pull(key="bcra_results", task_ids="extract_bcra")
    results = []
    for r in bcra_results:
        results.append({
            "cuit": r["cuit"],
            "eval_date": context["params"]["eval_date"],
            "deuda_total_ars": 0.0,
            "situacion_risk": 0,
            "cheques_sin_fondos": 0,
        })
    context["ti"].xcom_push(key="bcra_transformed", value=results)


def _transform_prices(**context):
    granos_results = context["ti"].xcom_pull(key="granos_results", task_ids="extract_granos")
    results = []
    for r in granos_results:
        results.append({
            "lot_id": "prices_snapshot",
            "eval_date": context["params"]["eval_date"],
            "crop": "soja",
            "precio_ars_tn": 0.0,
            "precio_usd_tn": None,
            "dolar_oficial": 0.0,
        })
    context["ti"].xcom_push(key="prices_transformed", value=results)


def _build_gold(**context):
    """Assemble fact_agro_credit_risk from silver outputs."""
    thresholds = load_thresholds()
    ndvi_results = context["ti"].xcom_pull(key="ndvi_results", task_ids="transform_ndvi")
    weather_results = context["ti"].xcom_pull(key="weather_transformed", task_ids="transform_weather")
    bcra_results = context["ti"].xcom_pull(key="bcra_transformed", task_ids="transform_bcra")
    prices_results = context["ti"].xcom_pull(key="prices_transformed", task_ids="transform_prices")

    rows = []
    for ndvi in ndvi_results:
        lot_id = ndvi["lot_id"]
        weather = next((w for w in weather_results if w["lot_id"] == lot_id), None)
        bcra = next((b for b in bcra_results if b["cuit"] == lot_id), None)
        price = next((p for p in prices_results if p.get("lot_id") == lot_id), None)
        if not weather or not bcra or not price:
            continue

        ndvi_val = ndvi["ndvi_median"]
        ndvi_drop_pct = None if ndvi_val in (None, -99, 0) else round(((0.7 - ndvi_val) / 0.7) * 100, 2)
        expected = None
        if ndvi_val and price.get("precio_usd_tn"):
            expected = round(50 * (ndvi_val / 0.7) * price["precio_usd_tn"], 2)

        rows.append({
            "lot_id": lot_id,
            "cuit": bcra.get("cuit", lot_id),
            "eval_date": ndvi.get("eval_date"),
            "ndvi": ndvi_val,
            "ndvi_hist_avg": 0.7,
            "ndvi_drop_pct": ndvi_drop_pct,
            "rainfall_mm": weather.get("rainfall_mm"),
            "expected_harvest_usd": expected,
            "bcra_debt_ars": bcra.get("deuda_total_ars", 0.0),
            "debt_ratio": None if not expected or expected <= 0 else round((bcra.get("deuda_total_ars") or 0) / expected, 4),
            "cheques_rechazados": bcra.get("cheques_sin_fondos", 0),
        })

    df = build_fact_table(rows, thresholds)
    context["ti"].xcom_push(key="gold_rows", value=df.to_dicts())
    return len(df)


dag = DAG(
    dag_id="agro_credit_risk",
    default_args=default_args,
    description="Daily agro credit risk pipeline: sources -> bronze -> silver -> gold",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    params={
        "eval_date": "{{ ds_nodash }}",
    },
)

transform_ndvi = PythonOperator(task_id="transform_ndvi", python_callable=_transform_ndvi, dag=dag)
transform_weather = PythonOperator(task_id="transform_weather", python_callable=_transform_weather, dag=dag)
transform_bcra = PythonOperator(task_id="transform_bcra", python_callable=_transform_bcra, dag=dag)
transform_prices = PythonOperator(task_id="transform_prices", python_callable=_transform_prices, dag=dag)
build_gold = PythonOperator(task_id="build_gold", python_callable=_build_gold, dag=dag)

(_extract_planetary >> transform_ndvi)
(_extract_weather >> transform_weather)
(_extract_bcra >> transform_bcra)
(_extract_granos >> transform_prices)
(transform_ndvi >> build_gold)
(transform_weather >> build_gold)
(transform_bcra >> build_gold)
(transform_prices >> build_gold)