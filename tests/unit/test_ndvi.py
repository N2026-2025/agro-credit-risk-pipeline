"""Unit tests for NDVI calculation with SCL cloud mask."""

import json
import numpy as np
import rasterio
from pathlib import Path

from src.silver.ndvi import calc_ndvi, process_ndvi


def test_calc_ndvi():
    """Test NDVI formula (NIR - RED) / (NIR + RED)."""
    b08 = np.array([0.5, 0.6, 0.7, 0.0])
    b04 = np.array([0.3, 0.4, 0.5, 0.0])
    ndvi = calc_ndvi(b08, b04)
    # Pixel 0: (0.5-0.3)/(0.5+0.3)=0.2/0.8=0.25
    # Pixel 1: (0.6-0.4)/(0.6+0.4)=0.2/1.0=0.2
    # Pixel 2: (0.7-0.5)/(0.7+0.5)=0.2/1.2≈0.1667
    # Pixel 3: denom=0 -> NaN
    assert ndvi[0] == 0.25
    assert abs(ndvi[1] - 0.2) < 1e-6
    assert abs(ndvi[2] - 0.166667) < 1e-4
    assert np.isnan(ndvi[3])


def test_process_ndvi_minimal():
    """Test NDVI processing with small synthetic GeoTIFF + polygon."""
    # Create synthetic GeoTIFF (4x4 pixels, 4 bands: B04,B08,SCL+extra)
    import tempfile
    tiff_path = Path(tempfile.mktemp(suffix=".tif"))
    geojson_path = Path(tempfile.mktemp(suffix=".geojson"))

    try:
        # Write a 4x4 GeoTIFF with known values
        with rasterio.open(
            tiff_path,
            "w",
            driver="GTiff",
            height=4,
            width=4,
            count=3,  # B08=band1, B04=band2, SCL=band3
            dtype="float32",
            crs="EPSG:4326",
            transform=rasterio.transform.from_bounds(
                -180, -90, 180, 90, 4, 4
            ),
        ) as src:
            # Band 1 (B08): all healthy vegetation
            src.write(np.full((4, 4), 0.7, dtype="float32"), 1)
            # Band 2 (B04): lower values -> positive NDVI
            src.write(np.full((4, 4), 0.3, dtype="float32"), 2)
            # Band 3 (SCL): all valid (no clouds)
            src.write(np.full((4, 4), 1, dtype="uint8"), 3)

        # Create a lot polygon covering all 4x4 pixels
        geojson = {
            "type": "Polygon",
            "coordinates": [[
                [-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]
            ]],
        }
        with open(geojson_path, "w") as f:
            json.dump(geojson, f)

        df = process_ndvi(str(tiff_path), str(geojson_path), lot_id="lot_test")
        assert "lot_id" in df.columns
        assert "ndvi_median" in df.columns
        assert "ndvi_count" in df.columns
        assert df["ndvi_median"][0] > 0  # should be positive NDVI
        assert df["ndvi_count"][0] > 0

    finally:
        if tiff_path.exists():
            tiff_path.unlink()
        if geojson_path.exists():
            geojson_path.unlink()


def test_process_ndvi_with_clouds():
    """Test that SCL clouds mask out pixels."""
    import tempfile
    tiff_path = Path(tempfile.mktemp(suffix=".tif"))
    geojson_path = Path(tempfile.mktemp(suffix=".geojson"))

    try:
        with rasterio.open(tiff_path, "w", driver="GTiff", height=4, width=4, count=3,
                          dtype="float32", crs="EPSG:4326") as src:
            # Band 1 B08: mixed
            src.write(np.full((4, 4), 0.7, dtype="float32"), 1)
            # Band 2 B04: mixed
            src.write(np.full((4, 4), 0.3, dtype="float32"), 2)
            # Band 3 SCL: pixels 0,1 = cloud (3), others valid (1)
            scl_data = np.full((4, 4), 1, dtype="uint8")
            scl_data[0, :] = 3  # row 0 = cloud
            scl_data[1, :] = 8  # row 1 = shadow
            src.write(scl_data, 3)

        geojson = {
            "type": "Polygon",
            "coordinates": [[
                [-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]
            ]],
        }
        with open(geojson_path, "w") as f:
            json.dump(geojson, f)

        df = process_ndvi(str(tiff_path), str(geojson_path), lot_id="lot_test")
        # Row 0 and 1 should be masked out by SCL; only rows 2,3 remain (8 pixels)
        assert df["ndvi_count"][0] == 8, f"Expected 8 valid pixels after cloud mask, got {df['ndvi_count'][0]}"

    finally:
        if tiff_path.exists():
            tiff_path.unlink()
        if geojson_path.exists():
            geojson_path.unlink()