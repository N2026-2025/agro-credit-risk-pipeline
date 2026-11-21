"""Silver layer: Weather join.

Joins lot-level weather from Open-Meteo Bronze raw JSON into Silver.
Reads: bronze/open_meteo/{date}/{lot_id}_weather.json
Writes: silver/weather/{date}/weather_lot.parquet
"""

import json
import logging
import sys

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def process_weather(lot_id: str, eval_date: str, weather_raw_path: str) -> pl.DataFrame:
    """Read raw weather JSON and extract values for one lot."""
    with open(weather_raw_path, "r") as f:
        raw = json.load(f)
    vals = extract_weather_values(raw)
    vals["lot_id"] = lot_id
    vals["eval_date"] = eval_date
    return pl.DataFrame([vals])


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python weather_join.py <lot_id> <eval_date> <weather_json_path>")
        sys.exit(1)

    lot_id, eval_date, weather_path = sys.argv[1], sys.argv[2], sys.argv[3]
    df = process_weather(lot_id, eval_date, weather_path)
    print(df.write_json())