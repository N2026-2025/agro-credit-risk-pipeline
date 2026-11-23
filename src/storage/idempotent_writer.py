"""
Idempotent writer for PostgreSQL targets.

Uses MERGE/UPSERT (ON CONFLICT) so re-running the pipeline for the same
date produces identical results without duplicates.
"""

import logging
from typing import Any, Optional

import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


def get_pg_conn() -> psycopg2.extensions.connection:
    import os
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        dbname=os.getenv("POSTGRES_DB", "agro"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def ensure_fact_table(conn: psycopg2.extensions.connection) -> None:
    """Create fact_agro_credit_risk with a unique constraint on (cuit, eval_date)."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fact_agro_credit_risk (
                id                SERIAL,
                lot_id            TEXT NOT NULL,
                cuit              TEXT NOT NULL,
                eval_date         TEXT NOT NULL,
                ndvi              DOUBLE PRECISION,
                ndvi_hist_avg     DOUBLE PRECISION,
                ndvi_drop_pct     DOUBLE PRECISION,
                crop              TEXT,
                critical_month    INTEGER,
                rainfall_mm       DOUBLE PRECISION,
                hectareas         DOUBLE PRECISION,
                precio_usd_tn     DOUBLE PRECISION,
                bcra_debt_ars     DOUBLE PRECISION,
                cheques_rechazados INTEGER,
                expected_harvest_usd DOUBLE PRECISION,
                debt_ratio        DOUBLE PRECISION,
                rinde_est_tn_ha   DOUBLE PRECISION,
                alert_agronomic   TEXT,
                alert_default     TEXT,
                processed_at      TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (cuit, eval_date)
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_eval_date
            ON fact_agro_credit_risk(eval_date);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_cuit
            ON fact_agro_credit_risk(cuit);
        """)
    conn.commit()


def upsert_fact_rows(
    conn: psycopg2.extensions.connection,
    rows: list[dict],
) -> int:
    """
    Upsert fact rows idempotently.

    Uses ON CONFLICT (cuit, eval_date) DO UPDATE so re-running for the same
    date replaces old values with new ones — no duplicates, identical output.
    """
    if not rows:
        return 0

    columns = [
        "lot_id", "cuit", "eval_date", "ndvi", "ndvi_hist_avg", "ndvi_drop_pct",
        "crop", "critical_month", "rainfall_mm", "hectareas", "precio_usd_tn",
        "bcra_debt_ars", "cheques_rechazados", "expected_harvest_usd",
        "debt_ratio", "rinde_est_tn_ha", "alert_agronomic", "alert_default",
    ]

    values = [
        tuple(
            row.get(col) for col in columns
        )
        for row in rows
    ]

    update_cols = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in columns if col not in ("cuit", "eval_date")
    )
    col_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO fact_agro_credit_risk ({col_list})
            VALUES %s
            ON CONFLICT (cuit, eval_date) DO UPDATE SET
                {update_cols},
                processed_at = NOW()
            """,
            values,
        )
    conn.commit()
    logger.info(f"Upserted {len(rows)} rows into fact_agro_credit_risk")
    return len(rows)