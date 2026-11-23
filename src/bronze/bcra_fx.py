"""Bronze: BCRA FX/reference extraction for treasury domain."""
import json
import logging
import os
import time

import requests
from minio import Minio

logger = logging.getLogger(__name__)


def get_minio_client():
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def fetch_bcra_series(series: str) -> dict:
    # BCRA estadisticas v3.0 style endpoint; tolerate failures in tests/offline.
    url = f"https://api.bcra.gob.ar/estadisticas/v3.0/monetarias/{series}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30, verify=False)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("bcra fx attempt %s %s status=%s", attempt + 1, series, resp.status_code)
        except requests.RequestException as e:
            logger.warning("bcra fx attempt %s %s error=%s", attempt + 1, series, e)
        time.sleep(2 ** attempt)
    return {}


def extract_bcra_fx(eval_date: str, series_ids: list[str] | None = None) -> dict:
    client = get_minio_client()
    bucket = "bronze"
    series_ids = series_ids or ["4", "5"]  # placeholders; configurable in real deploy
    results = {}
    for series in series_ids:
        data = fetch_bcra_series(series)
        key = f"fx_treasury/bcra_fx/{eval_date.replace('-', '')}/{series}.json"
        local = f"/tmp/bcra_fx_{series}_{eval_date}.json"
        payload = {"series": series, "eval_date": eval_date, "response": data}
        with open(local, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        client.fput_object(bucket, key, local)
        results[series] = key
    return results
