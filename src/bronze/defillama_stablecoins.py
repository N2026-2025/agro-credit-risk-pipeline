"""Bronze: DeFiLlama stablecoins extraction."""
import json
import logging
import os
import time

import requests
from minio import Minio

logger = logging.getLogger(__name__)
BASE_URL = "https://stablecoins.llama.fi"


def get_minio_client():
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def fetch_stablecoins() -> dict:
    url = f"{BASE_URL}/stablecoins?includePrices=true"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("defillama stablecoins attempt %s status=%s", attempt + 1, resp.status_code)
        except requests.RequestException as e:
            logger.warning("defillama stablecoins attempt %s error=%s", attempt + 1, e)
        time.sleep(2 ** attempt)
    return {}


def extract_defillama_stablecoins(eval_date: str) -> dict:
    client = get_minio_client()
    bucket = "bronze"
    key = f"fx_treasury/defillama/stablecoins/{eval_date.replace('-', '')}/stablecoins.json"
    data = fetch_stablecoins()
    local = f"/tmp/defillama_stablecoins_{eval_date}.json"
    with open(local, "w", encoding="utf-8") as f:
        json.dump(data, f)
    client.fput_object(bucket, key, local)
    return {"stablecoins_json": key, "count": len(data.get("peggedAssets", []))}
