"""Silver layer: BCRA join.

Reads Bronze BCRA JSON per CUIT and extracts key risk fields.
Writes to silver/bcra/{date}/bcra_lot.parquet
"""

import json
import logging
import sys

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_bcra_values(raw_json: dict) -> dict:
    """Extract deuda_total_ars, situacion_risk (1-5), cheques_sin_fondos from BCRA response."""
    # BCRA response structure varies; use safe getters
    deuda = raw_json.get("deudaTotal", raw_json.get("deuda_total_ars", 0))
    riesgo = raw_json.get("situacion", raw_json.get("situacion_risk", 0))
    cheques = raw_json.get("chequesRechazados", raw_json.get("cheques_sin_fondos", 0))
    return {
        "deuda_total_ars": float(deuda) if deuda else 0.0,
        "situacion_risk": int(riesgo) if riesgo else 0,
        "cheques_sin_fondos": int(cheques) if cheques else 0,
    }


def process_bcra(cuit: str, eval_date: str, bcra_raw_path: str) -> pl.DataFrame:
    with open(bcra_raw_path, "r") as f:
        raw = json.load(f)
    vals = extract_bcra_values(raw)
    vals["cuit"] = cuit
    vals["eval_date"] = eval_date
    return pl.DataFrame([vals])


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python bcra_join.py <cuit> <eval_date> <bcra_json_path>")
        sys.exit(1)
    cuit, eval_date, bcra_path = sys.argv[1], sys.argv[2], sys.argv[3]
    df = process_bcra(cuit, eval_date, bcra_path)
    print(df.write_json())