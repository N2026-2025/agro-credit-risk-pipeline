"""Silver layer: Weather join.

Joins lot-level weather from Open-Meteo Bronze raw JSON into Silver.
Reads: bronze/open_meteo/{date}/{lot_id}_weather.json
Writes: silver/weather/{date}/weather_lot.parquet
"""

import json
import os
import sys
from typing import Optional

import polars as pl

from src.schemas.contracts import (
    WeatherResponse,
    SilverWeatherRecord,
    validate_against_schema,
)
from src.schemas.quarantine import ensure_quarantine_table, quarantine_record
from src.storage.partitioning import get_partition_path

from src.observability.logging import get_logger


def extract_weather_values(raw_json: dict) -> dict:
    """Extract precipitation_sum, temp_max, temp_min from Open-Meteo response."""
    daily = raw_json.get("daily", {})
    dates = daily.get("time", [])
    precip = daily.get("precipitation_sum", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])

    if not dates:
        return {"rainfall_mm": None, "temp_max_c": None, "temp_min_c": None}

    dates[0]  # single-day request returns one entry
    return {
        "rainfall_mm": precip[0] if precip else None,
        "temp_max_c": temp_max[0] if temp_max else None,
        "temp_min_c": temp_min[0] if temp_min else None,
    }


def process_weather(
    lot_id: str,
    eval_date: str,
    weather_raw_path: str,
    pg_conn,
    pipeline_run_id: Optional[str] = None,
) -> pl.DataFrame:
    """Read raw weather JSON, validate, quarantine bad records, return valid DataFrame."""
    with open(weather_raw_path, "r") as f:
        raw = json.load(f)

    # Ensure quarantine table exists
    ensure_quarantine_table(pg_conn)

    # Validate against bronze schema
    raw_with_defaults = {
        "lot_id": lot_id,
        "lat": raw.get("latitude", 0.0),
        "lon": raw.get("longitude", 0.0),
        "eval_date": eval_date,
        **raw,
    }
    validated, errors = validate_against_schema(raw_with_defaults, WeatherResponse)
    if errors:
        quarantine_record(
            conn=pg_conn,
            source_system="weather",
            raw_payload=raw,
            validation_errors=errors,
            eval_date=eval_date,
            lot_id_or_cuit=lot_id,
            pipeline_run_id=pipeline_run_id,
        )
        logger.error("weather_record_quarantined", extra={"context": {"lot_id": lot_id, "errors": errors}})
        return pl.DataFrame()

    # Build Silver record
    vals = extract_weather_values(raw)
    silver_record = {
        "lot_id": lot_id,
        "eval_date": eval_date,
        **vals,
        "source": "open_meteo",
    }
    validated_silver, silver_errors = validate_against_schema(
        silver_record, SilverWeatherRecord
    )
    if silver_errors:
        quarantine_record(
            conn=pg_conn,
            source_system="weather_silver",
            raw_payload=silver_record,
            validation_errors=silver_errors,
            eval_date=eval_date,
            lot_id_or_cuit=lot_id,
            pipeline_run_id=pipeline_run_id,
        )
        logger.error("weather_silver_validation_failed", extra={"context": {"lot_id": lot_id, "errors": silver_errors}})
        return pl.DataFrame()

    return pl.DataFrame([validated_silver.model_dump()])


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python weather_join.py <lot_id> <eval_date> <weather_json_path>")
        sys.exit(1)

    lot_id, eval_date, weather_path = sys.argv[1], sys.argv[2], sys.argv[3]
    df = process_weather(lot_id, eval_date, weather_path, None)
    logger.info("cli_result", extra={"context": {"result": df.to_dicts()}})