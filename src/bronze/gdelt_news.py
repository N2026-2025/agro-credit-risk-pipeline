"""Bronze: GDELT news extraction (15-min window)."""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from minio import Minio

logger = logging.getLogger(__name__)
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def get_minio_client():
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def _fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")


def build_query(country: str, keywords: list[str]) -> str:
    kw = " OR ".join([f'"{k}"' for k in keywords])
    return f"({kw}) sourcecountry:{country}"


def fetch_gdelt_window(country: str, keywords: list[str], window_start: datetime, window_end: datetime, max_records: int = 75) -> list:
    query = build_query(country, keywords)
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "startdatetime": _fmt_dt(window_start),
        "enddatetime": _fmt_dt(window_end),
        "sort": "DateDesc",
    }
    for attempt in range(3):
        try:
            resp = requests.get(GDELT_DOC_URL, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("articles", []) if isinstance(data, dict) else []
            logger.warning("gdelt attempt %s %s status=%s", attempt + 1, country, resp.status_code)
        except requests.RequestException as e:
            logger.warning("gdelt attempt %s %s error=%s", attempt + 1, country, e)
        time.sleep(2 ** attempt)
    return []


def extract_gdelt_15m(window_end: datetime, countries: list[str], keywords: list[str], max_records: int = 75) -> dict:
    client = get_minio_client()
    bucket = "bronze"
    window_start = window_end - timedelta(minutes=15)
    results = {}
    for country in countries:
        articles = fetch_gdelt_window(country, keywords, window_start, window_end, max_records=max_records)
        qhash = hashlib.sha256(build_query(country, keywords).encode("utf-8")).hexdigest()[:16]
        key = f"fx_treasury/gdelt/{window_end.strftime('%Y%m%d')}/{country}_{window_end.strftime('%H%M')}_{qhash}.json"
        local = f"/tmp/gdelt_{country}_{window_end.strftime('%Y%m%d%H%M')}.json"
        payload = {
            "country": country,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "query_hash": qhash,
            "articles": articles,
        }
        with open(local, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        client.fput_object(bucket, key, local)
        results[country] = {"key": key, "count": len(articles), "query_hash": qhash}
    return results
