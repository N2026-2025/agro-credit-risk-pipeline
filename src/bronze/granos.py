"""Bronze layer: granos.ar prices extraction.

Fetches daily grain prices (soja, maíz, trigo pizarra Rosario + dólar mayorista).
Stores raw JSON to MinIO.

Usage:
    python src/bronze/granos.py <eval_date> [currency]
Example:
    python src/bronze/granos.py 2024-01-15 ARS
"""

import json
import logging
import os
import sys
import time

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


def fetch_granos(eval_date: str, currency: str = "ARS") -> dict:
    """Fetch grain prices from granos.ar API."""
    url = f"https://granos.ar/api/precios/{eval_date}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(f"Granos attempt {attempt+1}: status {resp.status_code}")
                time.sleep(2 ** attempt)
        except requests.RequestException as e:
            logger.warning(f"Granos attempt {attempt+1}: error {e}")
            time.sleep(2 ** attempt)
    logger.error(f"Failed to fetch granos prices for {eval_date} after 3 attempts")
    return {}


def extract_granos(eval_date: str) -> dict:
    """Extract prices snapshot for one eval_date."""
    client = get_minio_client()
    bucket = "bronze"
    date_str = eval_date.replace("-", "")
    key = f"granos/{date_str}/prices.json"

    prices = fetch_granos(eval_date)
    json_path = f"/tmp/prices_{eval_date}.json"
    with open(json_path, "w") as f:
        json.dump(prices, f)
    client.fput_object(bucket, key, json_path)

    return {"prices_json": key}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python granos.py <eval_date> [currency]")
        print("Example: python granos.py 2024-01-15 ARS")
        sys.exit(1)

    eval_date = sys.argv[1]
    result = extract_granos(eval_date)
    print(json.dumps(result))