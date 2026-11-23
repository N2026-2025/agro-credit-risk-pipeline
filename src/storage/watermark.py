"""
Watermark store for incremental loads.

Tracks the last processed date/ID per source so each pipeline run only
fetches new records from the 6 APIs. Stored in PostgreSQL.
"""

import logging
from datetime import datetime, date
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)


def get_pg_conn() -> psycopg2.extensions.connection:
    import os
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        dbname=os.getenv("POSTGRES_DB", "agro"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def ensure_watermark_table(conn: psycopg2.extensions.connection) -> None:
    """Create the watermark tracking table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_watermarks (
                source_name     TEXT PRIMARY KEY,
                last_processed_date TEXT NOT NULL,
                last_processed_id   TEXT,
                updated_at      TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_watermarks_source
            ON pipeline_watermarks(source_name);
        """)
    conn.commit()


def get_watermark(
    conn: psycopg2.extensions.connection, source_name: str
) -> Optional[str]:
    """Return the last processed date for a source, or None if never run."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT last_processed_date FROM pipeline_watermarks WHERE source_name = %s",
            (source_name,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def update_watermark(
    conn: psycopg2.extensions.connection,
    source_name: str,
    last_processed_date: str,
    last_processed_id: Optional[str] = None,
) -> None:
    """Upsert the watermark for a source after a successful run."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_watermarks
                (source_name, last_processed_date, last_processed_id, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (source_name) DO UPDATE
                SET last_processed_date = EXCLUDED.last_processed_date,
                    last_processed_id   = EXCLUDED.last_processed_id,
                    updated_at          = NOW()
            """,
            (source_name, last_processed_date, last_processed_id),
        )
    conn.commit()
    logger.info(
        f"Watermark updated for {source_name}: date={last_processed_date}, id={last_processed_id}"
    )