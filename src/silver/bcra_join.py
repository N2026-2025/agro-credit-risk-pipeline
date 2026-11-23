"""Silver layer: BCRA join.

Reads Bronze BCRA JSON per CUIT and extracts key risk fields.
Writes to silver/bcra/{date}/bcra_lot.parquet
"""

import json
import os
import sys
from typing import Optional

import polars as pl
from minio import Minio

from src.schemas.contracts import (
    BCRAResponse,
    SilverBCRARecord,
    validate_against_schema,
)
from src.schemas.quarantine import ensure_quarantine_table, quarantine_record
from src.storage.partitioning import get_partition_path

from src.observability.logging import get_logger


def get_minio_client() -> Minio:
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def extract_bcra_values(raw_json: dict) -> dict:
    """Extract deuda_total_ars, situacion_risk (1-5), cheques_sin_fondos from BCRA response."""
    # BCRA response structure varies; use safe getters
    deuda = raw_json.get("deudaTotal", raw_json.get("deuda_total_ars", 0))
    riesgo = raw_json.get("situacion", raw_json.get("situacion_risk", 0))
    cheques = raw_json.get("chequesRechazados", raw_json.get("cheques_sin_fondos", 0))
    return {
        "deuda_total_ars": float(deuda) if deuda else 0.0,
        "situacion_risk": int(riesgo) if riesgo else 0,
        "cheques_sin_fondos": int(cheques) if cheques else 0,
    }


def process_bcra(
    cuit: str,
    eval_date: str,
    bcra_raw_path: str,
    pg_conn,
    pipeline_run_id: Optional[str] = None,
) -> pl.DataFrame:
    """Read raw BCRA JSON, validate, quarantine bad records, return valid DataFrame."""
    with open(bcra_raw_path, "r") as f:
        raw = json.load(f)

    # Ensure quarantine table exists
    ensure_quarantine_table(pg_conn)

    # Step 1: Validate bronze-level response schema
    validated, errors = validate_against_schema(raw, BCRAResponse)
    if errors:
        quarantine_record(
            conn=pg_conn,
            source_system="bcra",
            raw_payload=raw,
            validation_errors=errors,
            eval_date=eval_date,
            lot_id_or_cuit=cuit,
            pipeline_run_id=pipeline_run_id,
        )
        logger.info("bcra_cuit_quarantined", extra={"context": {"cuit": cuit, "errors": errors}})
        return pl.DataFrame()

    # Step 2: Build Silver record and validate
    vals = extract_bcra_values(raw)
    silver_record = {
        "cuit": cuit,
        "eval_date": eval_date,
        **vals,
        "source": "bcra",
    }
    validated_silver, silver_errors = validate_against_schema(
        silver_record, SilverBCRARecord
    )
    if silver_errors:
        quarantine_record(
            conn=pg_conn,
            source_system="bcra_silver",
            raw_payload=silver_record,
            validation_errors=silver_errors,
            eval_date=eval_date,
            lot_id_or_cuit=cuit,
            pipeline_run_id=pipeline_run_id,
        )
        logger.error("bcra_silver_validation_failed", extra={"context": {"cuit": cuit, "errors": silver_errors}})
        return pl.DataFrame()

    return pl.DataFrame([validated_silver.model_dump()])


def write_partitioned(
    df: pl.DataFrame,
    base_path: str,
    eval_date: str,
    client: Minio,
    bucket: str = "silver",
) -> str:
    """Write DataFrame to partitioned Parquet path in MinIO."""
    partition_path = get_partition_path(base_path, eval_date)
    key = f"{partition_path}bcra_lot.parquet"
    local_path = f"/tmp/bcra_{eval_date.replace('-', '')}.parquet"
    df.write_parquet(local_path)
    client.fput_object(bucket, key, local_path)
    logger.info("write_partitioned", extra={"context": {"rows_written": len(df), "key": key}})
    return key


if __name__ == "__main__":
    if len(sys.argv) != 4:
        logger.error(
            "cli_usage",
            extra={
                "context": {
                    "usage": "python bcra_join.py <cuit> <eval_date> <bcra_json_path>",
                    "example": "python bcra_join.py 20-33333333-3 2024-01-15 /tmp/20240115_20-33333333-3.json",
                }
            },
        )
        sys.exit(1)
    cuit, eval_date, bcra_path = sys.argv[1], sys.argv[2], sys.argv[3]
    df = process_bcra(cuit, eval_date, bcra_path, None)
    logger.info("cli_result", extra={"context": {"result": df.to_dicts()}})