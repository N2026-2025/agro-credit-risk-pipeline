"""
Small-file compaction for Parquet data in MinIO.

When ingesting hourly from 6 APIs, thousands of tiny Parquet files accumulate.
This module compacts them into optimal-sized files (~128 MB) using DuckDB,
which also applies partition pruning benefits.
"""

import logging
import os
from typing import Optional

import duckdb

logger = logging.getLogger(__name__)


def compact_small_files(
    minio_endpoint: str = "localhost:9000",
    access_key: str = "minioadmin",
    secret_key: str = "minioadmin",
    bucket: str = "silver",
    target_file_size_mb: int = 128,
    prefix: Optional[str] = None,
) -> int:
    """
    Compact small Parquet files in a MinIO bucket into larger files.

    Uses DuckDB to read all Parquet files under a prefix and rewrite them
    as fewer, larger files. This reduces metadata overhead and improves
    query performance via partition pruning.

    Args:
        minio_endpoint: MinIO host:port
        access_key: MinIO access key
        secret_key: MinIO secret key
        bucket: Target bucket name
        target_file_size_mb: Target size per output file in MB
        prefix: Optional prefix (e.g. 'bcra/2026/11/') to compact only
                a specific partition. If None, compacts the whole bucket.

    Returns:
        Number of output files written.
    """
    conn = duckdb.connect()

    # Install and load httpfs for S3/MinIO access
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    conn.execute(f"SET s3_endpoint='{minio_endpoint}';")
    conn.execute("SET s3_access_key_id='{access_key}';")
    conn.execute("SET s3_secret_access_key='{secret_key}';")
    conn.execute("SET s3_use_ssl=false;")
    conn.execute("SET s3_url_style='path';")

    # Build the source glob pattern
    if prefix:
        source_glob = f"s3://{bucket}/{prefix}*.parquet"
    else:
        source_glob = f"s3://{bucket}/**/*.parquet"

    # Read all files and count them
    count_query = f"SELECT count(*) FROM read_parquet('{source_glob}')"
    file_count = conn.execute(count_query).fetchone()[0]
    logger.info(f"Found {file_count} Parquet files under {source_glob}")

    if file_count == 0:
        return 0

    # Compact: rewrite into larger files partitioned by existing hive structure
    # DuckDB will automatically produce well-sized output files
    output_pattern = f"s3://{bucket}/compacted/"
    if prefix:
        output_pattern += prefix.rstrip("/") + "/"

    conn.execute(f"""
        COPY (
            SELECT * FROM read_parquet('{source_glob}')
        ) TO '{output_pattern}' (FORMAT PARQUET, PARTITION_BY (year, month, day))
    """)

    # Count output files
    output_count_query = f"SELECT count(*) FROM read_parquet('{output_pattern}**/*.parquet')"
    output_count = conn.execute(output_count_query).fetchone()[0]
    logger.info(f"Compacted into {output_count} files under {output_pattern}")

    conn.close()
    return output_count