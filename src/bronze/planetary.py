"""Bronze layer: Planetary Computer STAC extraction for Sentinel-2 L2A.

Searches STAC for Sentinel-2 scenes intersecting lot bbox within ±3-day window
of eval_date; downloads B04+B08+B01+SCL bands as multi-band GeoTIFF.
Stores raw STAC item JSON + GeoTIFF to MinIO.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import planetary_computer
import pystac_client
import rasterio
from minio import Minio
from pystac import Item
import requests

logger = logging.getLogger(__name__)


def get_minio_client():
    """Create MinIO client from env."""
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
    )


def search_sentinel2(bbox, eval_date, max_cloud_cover=30):
    """Search Planetary Computer STAC for Sentinel-2 L2A scenes."""
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    
    start = eval_date - timedelta(days=3)
    end = eval_date + timedelta(days=3)
    
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{start.isoformat()}Z/{end.isoformat()}Z",
        query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        max_items=10,
    )
    
    items = list(search.items())
    logger.info(f"Found {len(items)} Sentinel-2 items for bbox={bbox}, date={eval_date}")
    return items


def download_bands(item: Item, bands=("B04", "B08", "B01", "SCL"), output_path=None):
    """Download specified bands from STAC item as GeoTIFF."""
    if output_path is None:
        output_path = f"/tmp/{item.id}.tif"
    
    assets = item.assets
    band_urls = {b: planetary_computer.sign(assets[b].href) for b in bands}
    
    # Read first band to get profile
    with rasterio.open(band_urls[bands[0]]) as src:
        profile = src.profile.copy()
        profile.update(count=len(bands), dtype="float32" if bands != ("SCL",) else "uint8")
    
    with rasterio.open(output_path, "w", **profile) as dst:
        for i, band in enumerate(bands, 1):
            with rasterio.open(band_urls[band]) as src:
                data = src.read(1)
                if band != "SCL":
                    data = data.astype("float32")
                dst.write(data, i)
    
    logger.info(f"Downloaded {len(bands)} bands to {output_path}")
    return output_path


def save_to_minio(client: Minio, bucket: str, key: str, file_path: str):
    """Upload file to MinIO bucket."""
    client.fput_object(bucket, key, file_path)
    logger.info(f"Uploaded {file_path} -> s3://{bucket}/{key}")


def extract_planetary(lot_id: str, bbox: list, eval_date: str) -> dict:
    """Main extraction function for one lot/date.
    
    Args:
        lot_id: Unique lot identifier
        bbox: [min_lon, min_lat, max_lon, max_lat]
        eval_date: YYYY-MM-DD string
    
    Returns:
        Dict with minio keys for raw JSON and GeoTIFF
    """
    client = get_minio_client()
    date_obj = datetime.strptime(eval_date, "%Y-%m-%d")
    bucket = "bronze"
    prefix = f"sentinel2/{eval_date.replace('-', '')}/"
    
    # Search and pick best scene (lowest cloud cover)
    items = search_sentinel2(bbox, date_obj)
    if not items:
        logger.warning(f"No Sentinel-2 scenes found for lot {lot_id} on {eval_date}")
        return {}
    
    best_item = min(items, key=lambda x: x.properties.get("eo:cloud_cover", 100))
    
    # Save STAC item JSON
    json_key = f"{prefix}{lot_id}_stac.json"
    json_path = f"/tmp/{lot_id}_stac.json"
    with open(json_path, "w") as f:
        json.dump(best_item.to_dict(), f)
    save_to_minio(client, bucket, json_key, json_path)
    
    # Download bands and save GeoTIFF
    tif_key = f"{prefix}{lot_id}_bands.tif"
    download_bands(best_item, output_path=f"/tmp/{lot_id}_bands.tif")
    save_to_minio(client, bucket, tif_key, f"/tmp/{lot_id}_bands.tif")
    
    return {"stac_json": json_key, "bands_tif": tif_key}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) != 4:
        print("Usage: python planetary.py <lot_id> <bbox> <eval_date>")
        print("Example: python planetary.py lot_01 '-60.7,-33.0,-60.6,-32.9' 2024-01-15")
        sys.exit(1)
    
    lot_id, bbox_str, eval_date = sys.argv[1], sys.argv[2], sys.argv[3]
    bbox = [float(x) for x in bbox_str.split(",")]
    result = extract_planetary(lot_id, bbox, eval_date)
    print(json.dumps(result))