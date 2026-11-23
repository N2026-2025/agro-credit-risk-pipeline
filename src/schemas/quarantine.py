"""
Quarantine / Dead Letter Queue for records that fail schema validation.

Invalid records are isolated in a PostgreSQL quarantine table with full
context (raw payload, validation errors, timestamp) so they can be
inspected and reprocessed after contract updates.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

import psycopg2
from psycopg2.extras import Json

from .contracts import QuarantineRecord

logger = logging.getLogger(__name__)


def get_pg_conn() -> psycopg2.extensions.connection:
    """Create a PostgreSQL connection from env vars."""
    import os
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        dbname=os.getenv("POSTGRES_DB", "agro"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def ensure_quarantine_table(conn: psycopg2.extensions.connection) -> None:
    """Create the quarantine table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quarantine_dlq (
                id              SERIAL PRIMARY KEY,
                source_system   TEXT NOT NULL,
                raw_payload     JSONB NOT NULL,
                validation_errors JSONB NOT NULL,
                eval_date       TEXT NOT NULL,
                lot_id_or_cuit  TEXT,
                quarantined_at  TIMESTAMPTZ DEFAULT NOW(),
                pipeline_run_id TEXT,
                schema_version  TEXT DEFAULT '1.0'
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarantine_eval_date
            ON quarantine_dlq(eval_date);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarantine_source
            ON quarantine_dlq(source_system);
        """)
    conn.commit()


def quarantine_record(
    conn: psycopg2.extensions.connection,
    source_system: str,
    raw_payload: dict,
    validation_errors: list[str],
    eval_date: str,
    lot_id_or_cuit: Optional[str] = None,
    pipeline_run_id: Optional[str] = None,
) -> int:
    """
    Insert a failed record into the quarantine table.

    Returns the quarantine row ID.
    """
    qr = QuarantineRecord(
        source_system=source_system,
        raw_payload=raw_payload,
        validation_errors=validation_errors,
        eval_date=eval_date,
        lot_id_or_cuit=lot_id_or_cuit,
        pipeline_run_id=pipeline_run_id,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO quarantine_dlq
                (source_system, raw_payload, validation_errors, eval_date,
                 lot_id_or_cuit, quarantined_at, pipeline_run_id, schema_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                qr.source_system,
                Json(qr.raw_payload),
                Json(qr.validation_errors),
                qr.eval_date,
                qr.lot_id_or_cuit,
                qr.quarantined_at,
                qr.pipeline_run_id,
                qr.schema_version,
            ),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    logger.warning(
        f"Quarantined record id={row_id} source={source_system} "
        f"eval_date={eval_date} errors={validation_errors}"
    )
    return row_id


def get_quarantined_records(
    conn: psycopg2.extensions.connection,
    source_system: Optional[str] = None,
    eval_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Retrieve quarantined records for inspection/reprocessing."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        query = """
            SELECT id, source_system, raw_payload, validation_errors,
                   eval_date, lot_id_or_cuit, quarantined_at,
                   pipeline_run_id, schema_version
            FROM quarantine_dlq
            WHERE 1=1
        """
        params: list[Any] = []
        if source_system:
            query += " AND source_system = %s"
            params.append(source_system)
        if eval_date:
            query += " AND eval_date = %s"
            params.append(eval_date)
        query += " ORDER BY quarantined_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]