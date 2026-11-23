"""Bronze: DeFiLlama yields extraction."""
import json
import logging
import os
import time

import requests
from minio import Minio

logger = logging.getLogger(__name__)
YIELDS_URL = "https://yields.llama.fi/pools"


def get_minio_client():
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def fetch_yields() -> dict:
    for attempt in range(3):
        try:
            resp = requests.get(YIELDS_URL, timeout=45)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("defillama yields attempt %s status=%s", attempt + 1, resp.status_code)
        except requests.RequestException as e:
            logger.warning("defillama yields attempt %s error=%s", attempt + 1, e)
        time.sleep(2 ** attempt)
    return {}


def extract_defillama_yields(eval_date: str) -> dict:
    client = get_minio_client()
    bucket = "bronze"
    key = f"fx_treasury/defillama/yields/{eval_date.replace('-', '')}/yields.json"
    data = fetch_yields()
    local = f"/tmp/defillama_yields_{eval_date}.json"
    with open(local, "w", encoding="utf-8") as f:
        json.dump(data, f)
    client.fput_object(bucket, key, local)
    return {"yields_json": key, "count": len(data.get("data", []))}
