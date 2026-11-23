"""
Partitioning helpers for intelligent storage layout.

Partitions data by year/month/day (and optionally region) to enable
partition pruning — queries only read the files they need.
"""

from datetime import date, datetime
from typing import Optional


def get_partition_path(
    base_path: str,
    eval_date: str,
    region: Optional[str] = None,
) -> str:
    """
    Build a Hive-style partition path.

    Args:
        base_path: Base path (e.g. 'silver/bcra' or 's3://bucket/silver')
        eval_date: Date string in YYYY-MM-DD format
        region: Optional region name for secondary partitioning

    Returns:
        Partition path like 'silver/bcra/year=2026/month=11/day=22/'
        or with region: 'silver/bcra/region=rosario/year=2026/month=11/day=22/'
    """
    dt = datetime.strptime(eval_date, "%Y-%m-%d")
    parts = [
        f"year={dt.year}",
        f"month={dt.month:02d}",
        f"day={dt.day:02d}",
    ]
    if region:
        parts.insert(0, f"region={region}")
    return f"{base_path}/" + "/".join(parts) + "/"


def get_partition_filter(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region: Optional[str] = None,
) -> str:
    """
    Build a SQL WHERE clause for partition pruning.

    Returns a filter string that can be appended to a query to skip
    irrelevant partitions (e.g. year >= 2026 AND month >= 11).
    """
    conditions = []
    if start_date:
        dt = datetime.strptime(start_date, "%Y-%m-%d")
        conditions.append(f"year >= {dt.year}")
        if end_date is None or dt.month > 1:
            conditions.append(f"(year > {dt.year} OR month >= {dt.month:02d})")
    if end_date:
        dt = datetime.strptime(end_date, "%Y-%m-%d")
        conditions.append(f"year <= {dt.year}")
        if start_date is None or dt.month < 12:
            conditions.append(f"(year < {dt.year} OR month <= {dt.month:02d})")
    if region:
        conditions.append(f"region = '{region}'")
    return " AND ".join(conditions) if conditions else "1=1"