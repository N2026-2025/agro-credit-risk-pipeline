"""Silver layer: Prices join (granos.ar + dólar mayorista).

Joins lot-level crop + eval_date with grain prices from granos.ar and
dólar mayorista. Computes precio_usd_tn per crop.

Writes: silver/prices/{date}/prices_lot.parquet
"""

import json
import logging
import os
import sys
from pathlib import Path

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_thresholds(path: str = "config/thresholds.yml") -> dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def extract_prices_from_granos(raw_json: dict, thresholds: dict) -> dict:
    """Extract precios pizarra rosario and dolar oficial from granos.ar response."""
    # granos.ar API returns nested structure; adapt as needed
    precios = raw_json.get("precios", {})
    dolar = raw_json.get("dolar_oficial", 0)

    soja_ars = precios.get("soja", {}).get("precio_ars_tn", 0)
    maiz_ars = precios.get("maiz", {}).get("precio_ars_tn", 0)
    trigo_ars = precios.get("trigo", {}).get("precio_ars_tn", 0)

    soja_usd = soja_ars / dolar if dolar and dolar > 0 else None
    maiz_usd = maiz_ars / dolar if dolar and dolar > 0 else None
    trigo_usd = trigo_ars / dolar if dolar and dolar > 0 else None

    return {
        "soja_ars_tn": soja_ars,
        "maiz_ars_tn": maiz_ars,
        "trigo_ars_tn": trigo_ars,
        "dolar_oficial": float(dolar) if dolar else 0.0,
        "soja_usd_tn": soja_usd,
        "maiz_usd_tn": maiz_usd,
        "trigo_usd_tn": trigo_usd,
    }


def process_prices(lot_id: str, cuit: str, crop: str, eval_date: str,
                   prices_raw_path: str, thresholds: dict) -> pl.DataFrame:
    with open(prices_raw_path, "r") as f:
        raw = json.load(f)
    prices = extract_prices_from_granos(raw, thresholds)

    # Look up crop price
    precio_ars = prices.get(f"{crop}_ars_tn", 0)
    precio_usd = prices.get(f"{crop}_usd_tn", None)
    dolar = prices.get("dolar_oficial", 0)

    return pl.DataFrame({
        "lot_id": [lot_id],
        "cuit": [cuit],
        "crop": [crop],
        "eval_date": [eval_date],
        "precio_ars_tn": [precio_ars],
        "precio_usd_tn": [precio_usd],
        "dolar_oficial": [dolar],
    })


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: python prices_join.py <lot_id> <cuit> <crop> <eval_date> <prices_json_path> [thresholds_yaml]")
        sys.exit(1)

    lot_id, cuit, crop, eval_date = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    prices_path = sys.argv[5]
    thresholds_path = sys.argv[6] if len(sys.argv) > 6 else "config/thresholds.yml"
    thresholds = load_thresholds(thresholds_path)

    df = process_prices(lot_id, cuit, crop, eval_date, prices_path, thresholds)
    print(df.write_json())