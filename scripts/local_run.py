"""Local pipeline runner (offline smoke test).

Runs the full Bronze -> Silver -> Gold pipeline with sample data, no external APIs.
Usage:
    python scripts/local_run.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.thresholds import load_thresholds
from src.gold.fact import build_fact_table

# Sample rows covering: normal, agronomic alert, default alert
SAMPLE_ROWS = [
    {
        "lot_id": "lot_01",
        "cuit": "20-11111111-1",
        "eval_date": "2024-01-15",
        "ndvi": 0.65,
        "ndvi_hist_avg": 0.70,
        "crop": "soja",
        "critical_month": 1,
        "rainfall_mm": 25.0,
        "hectareas": 50.0,
        "precio_usd_tn": 450.0,
        "bcra_debt_ars": 30000.0,
        "cheques_rechazados": 0,
    },
    {
        "lot_id": "lot_02",
        "cuit": "20-22222222-2",
        "eval_date": "2024-01-15",
        "ndvi": 0.45,
        "ndvi_hist_avg": 0.70,
        "crop": "soja",
        "critical_month": 1,
        "rainfall_mm": 10.0,
        "hectareas": 60.0,
        "precio_usd_tn": 450.0,
        "bcra_debt_ars": 20000.0,
        "cheques_rechazados": 0,
    },
    {
        "lot_id": "lot_03",
        "cuit": "20-33333333-3",
        "eval_date": "2024-01-15",
        "ndvi": 0.65,
        "ndvi_hist_avg": 0.70,
        "crop": "maíz",
        "critical_month": 1,
        "rainfall_mm": 30.0,
        "hectareas": 40.0,
        "precio_usd_tn": 250.0,
        "bcra_debt_ars": 1000000.0,
        "cheques_rechazados": 2,
    },
]


def main():
    thresholds = load_thresholds()
    df = build_fact_table(SAMPLE_ROWS, thresholds)
    print("\n=== Gold Fact Table (fact_agro_credit_risk) ===\n")
    print(f"Rows: {len(df)}\n")
    print(df.select(["lot_id", "cuit", "ndvi", "ndvi_drop_pct", "expected_harvest_usd", "debt_ratio", "alert_agronomic", "alert_default"]).write_json())
    alerts = df.filter(
        (df["alert_agronomic"].is_not_null()) | (df["alert_default"].is_not_null())
    )
    print(f"\n=== Active Alerts ({len(alerts)}) ===\n")
    for row in alerts.to_dicts():
        print(f"  - {row['lot_id']}: agronomic={row['alert_agronomic']}, default={row['alert_default']}, debt_ratio={row['debt_ratio']}")


if __name__ == "__main__":
    main()