"""
Data lineage tracking for the agro-credit risk pipeline.

Tracks column-level lineage from each of the 6 source APIs through
Bronze -> Silver -> Gold transformations, enabling dbt-docs-style
visual lineage graphs and impact analysis.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ColumnLineage:
    """Represents the lineage of a single column from source to target."""

    def __init__(
        self,
        column_name: str,
        source_system: str,
        source_column: str,
        target_column: str,
        transformation: str,
        business_meaning: str,
        unit_of_measure: Optional[str] = None,
        owner: Optional[str] = None,
    ):
        self.column_name = column_name
        self.source_system = source_system
        self.source_column = source_column
        self.target_column = target_column
        self.transformation = transformation
        self.business_meaning = business_meaning
        self.unit_of_measure = unit_of_measure
        self.owner = owner
        self.lineage_timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "column_name": self.column_name,
            "source_system": self.source_system,
            "source_column": self.source_column,
            "target_column": self.target_column,
            "transformation": self.transformation,
            "business_meaning": self.business_meaning,
            "unit_of_measure": self.unit_of_measure,
            "owner": self.owner,
            "lineage_timestamp": self.lineage_timestamp,
        }


class LineageTracker:
    """Tracks and exports column-level lineage across the pipeline."""

    def __init__(self):
        self._lineage: list[ColumnLineage] = []

    def add_lineage(
        self,
        column_name: str,
        source_system: str,
        source_column: str,
        target_column: str,
        transformation: str,
        business_meaning: str,
        unit_of_measure: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> None:
        """Register a column's journey from source to target."""
        lineage = ColumnLineage(
            column_name=column_name,
            source_system=source_system,
            source_column=source_column,
            target_column=target_column,
            transformation=transformation,
            business_meaning=business_meaning,
            unit_of_measure=unit_of_measure,
            owner=owner,
        )
        self._lineage.append(lineage)
        logger.info(
            f"Lineage: {source_system}.{source_column} -> {target_column} "
            f"({transformation})"
        )

    def get_lineage(self) -> list[dict]:
        """Return all recorded lineage as a list of dicts."""
        return [l.to_dict() for l in self._lineage]

    def export_json(self, path: str) -> None:
        """Export lineage graph to a JSON file (compatible with dbt docs)."""
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "pipeline": "agro_credit_risk",
            "lineage": self.get_lineage(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Lineage exported to {path} ({len(self._lineage)} columns)")

    def get_lineage_by_target(self, target_column: str) -> list[dict]:
        """Get all lineage entries that produce a given target column."""
        return [
            l.to_dict() for l in self._lineage if l.target_column == target_column
        ]

    def get_lineage_by_source(self, source_system: str) -> list[dict]:
        """Get all lineage entries originating from a source system."""
        return [
            l.to_dict() for l in self._lineage if l.source_system == source_system
        ]


# Global tracker instance for use across the pipeline
lineage_tracker = LineageTracker()