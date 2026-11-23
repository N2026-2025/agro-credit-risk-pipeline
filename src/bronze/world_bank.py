"""Bronze: World Bank indicators extraction."""
import json
import logging
import os
import time

import requests
from minio import Minio

logger = logging.getLogger(__name__)
WB_BASE = "https://api.worldbank.org/v2"


def get_minio_client():
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def fetch_indicator(country_code: str, indicator: str, per_page: int = 200) -> list:
    url = f"{WB_BASE}/country/{country_code}/indicator/{indicator}?format=json&per_page={per_page}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data[1] if isinstance(data, list) and len(data) > 1 and data[1] else []
            logger.warning("world bank attempt %s %s/%s status=%s", attempt + 1, country_code, indicator, resp.status_code)
        except requests.RequestException as e:
            logger.warning("world bank attempt %s %s/%s error=%s", attempt + 1, country_code, indicator, e)
        time.sleep(2 ** attempt)
    return []


def extract_world_bank(eval_date: str, country_codes: list[str], indicators: dict[str, str]) -> dict:
    client = get_minio_client()
    bucket = "bronze"
    results = {}
    for country in country_codes:
        country_rows = []
        for name, indicator in indicators.items():
            rows = fetch_indicator(country, indicator)
            country_rows.append({"indicator_name": name, "indicator_code": indicator, "rows": rows})
        key = f"fx_treasury/world_bank/{eval_date.replace('-', '')}/{country}.json"
        local = f"/tmp/world_bank_{country}_{eval_date}.json"
        with open(local, "w", encoding="utf-8") as f:
            json.dump({"country": country, "eval_date": eval_date, "indicators": country_rows}, f)
        client.fput_object(bucket, key, local)
        results[country] = key
    return results
