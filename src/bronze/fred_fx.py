"""Bronze: FRED series extraction."""
import json
import logging
import os
import time

import requests
from minio import Minio

logger = logging.getLogger(__name__)
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_minio_client():
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def fetch_fred_series(series_id: str, api_key: str, observation_start: str | None = None) -> list:
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    if observation_start:
        params["observation_start"] = observation_start
    for attempt in range(3):
        try:
            resp = requests.get(FRED_URL, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("observations", [])
            logger.warning("fred attempt %s %s status=%s", attempt + 1, series_id, resp.status_code)
        except requests.RequestException as e:
            logger.warning("fred attempt %s %s error=%s", attempt + 1, series_id, e)
        time.sleep(2 ** attempt)
    return []


def extract_fred(eval_date: str, series_map: dict[str, str], api_key: str | None = None) -> dict:
    client = get_minio_client()
    bucket = "bronze"
    api_key = api_key or os.getenv("FRED_API_KEY", "")
    results = {}
    for name, series_id in series_map.items():
        obs = fetch_fred_series(series_id, api_key) if api_key else []
        key = f"fx_treasury/fred/{eval_date.replace('-', '')}/{series_id}.json"
        local = f"/tmp/fred_{series_id}_{eval_date}.json"
        payload = {"series_name": name, "series_id": series_id, "observations": obs, "eval_date": eval_date}
        with open(local, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        client.fput_object(bucket, key, local)
        results[name] = {"key": key, "count": len(obs)}
    return results
