"""Bronze layer: BCRA Central de Deudores extraction.

Queries BCRA API for total debt and cheques rejected per CUIT.
No authentication required; stores raw JSON to MinIO.

Usage:
    python src/bronze/bcra.py <cuit> <eval_date>
Example:
    python src/bronze/bcra.py 20-33333333-3 2024-01-15
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


def fetch_bcra_deuda(cuit: str) -> dict:
    """Query BCRA for total debt in ARS per CUIT."""
    base = "https://bcra.gob.ar/centraldeudores/v1.0"
    url = f"{base}/Deudas/{cuit}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                logger.warning(f"CUIT {cuit} not found in BCRA Deudas")
                return {}
            else:
                logger.warning(f"BCRA Deudas attempt {attempt+1}: status {resp.status_code}")
                time.sleep(2 ** attempt)
        except requests.RequestException as e:
            logger.warning(f"BCRA Deudas attempt {attempt+1}: error {e}")
            time.sleep(2 ** attempt)
    logger.error(f"Failed to fetch BCRA deuda for CUIT {cuit} after 3 attempts")
    return {}


def fetch_bcra_cheques_rechazados(cuit: str) -> dict:
    """Query BCRA for rejected checks per CUIT."""
    base = "https://bcra.gob.ar/centraldeudores/v1.0"
    url = f"{base}/ChequesRechazados/{cuit}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                logger.warning(f"CUIT {cuit} not found in BCRA ChequesRechazados")
                return {}
            else:
                logger.warning(f"BCRA ChequesRechazados attempt {attempt+1}: status {resp.status_code}")
                time.sleep(2 ** attempt)
        except requests.RequestException as e:
            logger.warning(f"BCRA ChequesRechazados attempt {attempt+1}: error {e}")
            time.sleep(2 ** attempt)
    logger.error(f"Failed to fetch BCRA cheques rechazados for CUIT {cuit} after 3 attempts")
    return {}


def extract_bcra(cuit: str, eval_date: str) -> dict:
    """Extract BCRA data for one CUIT/eval_date."""
    client = get_minio_client()
    bucket = "bronze"
    key = f"bcra/{eval_date.replace('-', '')}/{cuit.replace('-', '')}.json"

    deuda = fetch_bcra_deuda(cuit)
    cheques = fetch_bcra_cheques_rechazados(cuit)

    # Merge into single record
    merged = {**deuda, **cheques}
    merged["cuit"] = cuit
    merged["eval_date"] = eval_date

    json_path = f"/tmp/{cuit}_bcra.json"
    with open(json_path, "w") as f:
        json.dump(merged, f)
    client.fput_object(bucket, key, json_path)

    return {"bcra_json": key}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python bcra.py <cuit> <eval_date>")
        print("Example: python bcra.py 20-33333333-3 2024-01-15")
        sys.exit(1)

    cuit, eval_date = sys.argv[1], sys.argv[2]
    result = extract_bcra(cuit, eval_date)
    print(json.dumps(result))