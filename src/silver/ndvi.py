"""Silver layer: NDVI calculation with SCL cloud mask.

Reads Bronze GeoTIFF (bands: B04, B08, SCL), applies SCL cloud mask,
computes per-pixel NDVI = (B08 - B04) / (B08 + B04), clips to lot polygon,
and aggregates to lot-level median NDVI.

Usage:
    python src/silver/ndvi.py <tiff_path> <geojson_path> [lot_id]
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
import geopandas as gpd
import polars as pl

from src.schemas.contracts import (
    SilverNDVIRecord,
    validate_against_schema,
)
from src.schemas.quarantine import ensure_quarantine_table, quarantine_record

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SCL classes that are NOT clouds/shadow (keep valid land pixels)
VALID_SCL = [0, 1, 2, 4, 5, 6, 7, 9, 10, 11]
FILL_NDVI = -99.0


def calc_ndvi(b08: np.ndarray, b04: np.ndarray) -> np.ndarray:
    """Compute NDVI = (NIR - RED) / (NIR + RED). Invalid where denom==0."""
    denom = b08 + b04
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(denom != 0, (b08 - b04) / denom, np.nan)
    return ndvi


def process_ndvi(
    tiff_path: str,
    geojson_path: str,
    lot_id: str = None,
    eval_date: Optional[str] = None,
    pg_conn=None,
    pipeline_run_id: Optional[str] = None,
) -> pl.DataFrame:
    """Full NDVI processing pipeline; returns lot-level median NDVI."""
    with rasterio.open(tiff_path) as src:
        # Clip to lot polygon first
        gdf = gpd.read_file(geojson_path)
        if gdf.crs != src.crs:
            gdf = gdf.to_crs(src.crs)

        from rasterio.mask import mask as rio_mask
        clipped, _ = rio_mask(src, gdf.geometry, crop=True, filled=False)
        # clipped is a MaskedArray with shape (bands, height, width)
        b08 = np.ma.filled(clipped[0], np.nan).astype("float32")
        b04 = np.ma.filled(clipped[1], np.nan).astype("float32")
        scl = np.ma.filled(clipped[2], 0).astype("uint8")

        # Apply SCL cloud mask: set invalid pixels to NaN
        valid_mask = np.isin(scl, VALID_SCL)
        b08m = np.where(valid_mask, b08, np.nan)
        b04m = np.where(valid_mask, b04, np.nan)
        ndvi = calc_ndvi(b08m, b04m)
        valid_ndvi = ndvi[~np.isnan(ndvi)]

    if len(valid_ndvi) == 0:
        result = {
            "lot_id": lot_id or Path(geojson_path).stem,
            "ndvi_median": FILL_NDVI,
            "ndvi_count": 0,
        }
    else:
        result = {
            "lot_id": lot_id or Path(geojson_path).stem,
            "ndvi_median": round(float(np.nanmedian(valid_ndvi)), 6),
            "ndvi_count": int(len(valid_ndvi)),
        }

    # Validate against SilverNDVIRecord schema
    if eval_date:
        result["eval_date"] = eval_date
        result["source"] = "planetary_computer"
        validated, errors = validate_against_schema(result, SilverNDVIRecord)
        if errors:
            if pg_conn:
                ensure_quarantine_table(pg_conn)
                quarantine_record(
                    conn=pg_conn,
                    source_system="ndvi_silver",
                    raw_payload=result,
                    validation_errors=errors,
                    eval_date=eval_date,
                    lot_id_or_cuit=lot_id,
                    pipeline_run_id=pipeline_run_id,
                )
            logger.error(f"NDVI silver validation failed for lot {lot_id}: {errors}")
            return pl.DataFrame()

    return pl.DataFrame([result])


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python ndvi.py <tiff_path> <geojson_path> [lot_id]")
        sys.exit(1)

    tiff_path, geojson_path = sys.argv[1], sys.argv[2]
    lot_id = sys.argv[3] if len(sys.argv) > 3 else None
    df = process_ndvi(tiff_path, geojson_path, lot_id)
    print(df.write_json())
