"""Bronze layer: Open-Meteo Archive extraction.

Queries Open-Meteo archive API for daily weather at lot centroid lat/lon.
Stores raw JSON to MinIO.

Usage:
    python src/bronze/weather.py <lat> <lon> <eval_date>
Example:
    python src/bronze/weather.py 34.0 -60.7 2024-01-15
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from minio import Minio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_minio_client():
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def fetch_weather(lat: float, lon: float, eval_date: str) -> dict:
    """Query Open-Meteo archive for daily weather."""
    start = eval_date
    end = eval_date
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
        f"&start_date={start}"
        f"&end_date={end}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"Fetched weather for lat={lat}, lon={lon}, date={eval_date}: {data}")
    return data


def extract_weather(lot_id: str, lat: float, lon: float, eval_date: str) -> dict:
    """Extract weather data for one lot/date."""
    client = get_minio_client()
    date_obj = datetime.strptime(eval_date, "%Y-%m-%d")
    bucket = "bronze"
    date_str = date_obj.strftime("%Y%m%d")
    prefix = f"open_meteo/{date_str}/"
    key = f"{prefix}{lot_id}_weather.json"
    
    weather = fetch_weather(lat, lon, eval_date)
    json_path = f"/tmp/{lot_id}_weather.json"
    with open(json_path, "w") as f:
        json.dump(weather, f)
    save_to_minio(client, bucket, key, json_path)
    
    return {"weather_json": key}


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python weather.py <lot_id> <lat> <lon> <eval_date>")
        sys.exit(1)
    
    lot_id, lat_str, lon_str, eval_date = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    result = extract_weather(lot_id, float(lat_str), float(lon_str), eval_date)
    print(json.dumps(result))