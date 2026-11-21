"""Integration test: Full pipeline from seed -> fact table (offline, mocked data)."""


import polars as pl

from config.thresholds import load_thresholds
from src.gold.fact import build_fact_table


def _sample_rows():
    """Return 3 sample lots covering: normal, agronomic alert, default alert."""
    return [
        # Lot 1: Normal (healthy NDVI, enough rain, LOW debt)
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
            "bcra_debt_ars": 30000.0,  # low debt -> no default alert
            "cheques_rechazados": 0,
        },
        # Lot 2: Agronomic alert (NDVI drop >20%, low rain in Jan), LOW debt
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
            "bcra_debt_ars": 20000.0,  # low debt -> no default alert
            "cheques_rechazados": 0,
        },
        # Lot 3: Default alert (debt > 70% of expected harvest)
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
            "bcra_debt_ars": 1000000.0,  # high debt
            "cheques_rechazados": 2,
        },
    ]


def test_build_fact_table_with_alerts():
    """Run build_fact_table on sample rows and verify all columns + alerts."""
    thresholds = load_thresholds()
    rows_in = _sample_rows()
    df = build_fact_table(rows_in, thresholds)

    # Basic shape
    assert df.height == 3, f"Expected 3 rows, got {df.height}"
    expected_cols = {
        "lot_id", "cuit", "eval_date", "ndvi", "ndvi_hist_avg", "ndvi_drop_pct",
        "crop", "critical_month", "rainfall_mm", "hectareas", "precio_usd_tn",
        "bcra_debt_ars", "cheques_rechazados", "expected_harvest_usd", "debt_ratio",
        "alert_agronomic", "alert_default",
    }
    assert expected_cols.issubset(set(df.columns)), f"Missing columns: {expected_cols - set(df.columns)}"

    # Lot 1 (normal): no alerts
    r1 = df.filter(pl.col("lot_id") == "lot_01").row(0, named=True)
    assert r1["alert_agronomic"] is None, f"Lot 1 alert_agronomic={r1['alert_agronomic']}"
    assert r1["alert_default"] is None, f"Lot 1 alert_default={r1['alert_default']}"
    assert r1["ndvi_drop_pct"] == 7.14  # (0.70-0.65)/0.70*100

    # Lot 2 (agronomic): alert_agronomic='Alta', no default
    r2 = df.filter(pl.col("lot_id") == "lot_02").row(0, named=True)
    assert r2["alert_agronomic"] == "Alta", f"Lot 2 alert_agronomic={r2['alert_agronomic']}"
    assert r2["alert_default"] is None, f"Lot 2 alert_default={r2['alert_default']}"
    assert r2["ndvi_drop_pct"] == 35.71  # > 20% threshold

    # Lot 3 (default): alert_default='Preventiva', no agronomic
    r3 = df.filter(pl.col("lot_id") == "lot_03").row(0, named=True)
    assert r3["alert_agronomic"] is None, f"Lot 3 alert_agronomic={r3['alert_agronomic']}"
    assert r3["alert_default"] == "Preventiva", f"Lot 3 alert_default={r3['alert_default']}"
    assert r3["cheques_rechazados"] == 2
    # debt_ratio = 1000000 / (40 * 8.0 * (0.65/0.7) * 250) approx
    # Expected harvest: 40 * 8.0 * (0.65/0.7) * 250 ≈ 40 * 7.43 * 250 = 74,285
    # debt_ratio = 1,000,000 / 74,285 ≈ 13.5 > 0.7 -> Preventiva
    assert r3["debt_ratio"] is not None and r3["debt_ratio"] > 0.7


def test_expected_harvest_calculation():
    """Verify expected_harvest_usd = ha * rinde_est * precio_usd_tn."""
    thresholds = load_thresholds()
    row = {
        "lot_id": "test",
        "cuit": "20-00000000-0",
        "eval_date": "2024-01-15",
        "ndvi": 0.7,
        "ndvi_hist_avg": 0.7,
        "crop": "soja",
        "critical_month": 1,
        "rainfall_mm": 20,
        "hectareas": 100,
        "precio_usd_tn": 400,
        "bcra_debt_ars": 0,
        "cheques_rechazados": 0,
    }
    df = build_fact_table([row], thresholds)
    r = df.row(0, named=True)
    # rinde = base(3.0) * (0.7/0.7) * clamp = 3.0
    # expected = 100 * 3.0 * 400 = 120,000
    assert r["rinde_est_tn_ha"] == 3.0
    assert r["expected_harvest_usd"] == 120000.0


def test_crop_specific_rainfall_threshold():
    """Maize uses rainfall_maiz_mm (20), Soy uses rainfall_soja_mm (15)."""
    thresholds = load_thresholds()
    # Soy: rain=15 (threshold) -> NOT < threshold -> no alert
    row_soja = {
        "lot_id": "s", "cuit": "1", "eval_date": "2024-01-15",
        "ndvi": 0.4, "ndvi_hist_avg": 0.7, "crop": "soja",
        "critical_month": 1, "rainfall_mm": 15, "hectareas": 50,
        "precio_usd_tn": 400, "bcra_debt_ars": 0, "cheques_rechazados": 0,
    }
    df_soja = build_fact_table([row_soja], thresholds)
    assert df_soja["alert_agronomic"][0] is None

    # Soy: rain=14 (<15) -> ALERT
    row_soja["rainfall_mm"] = 14
    df_soja2 = build_fact_table([row_soja], thresholds)
    assert df_soja2["alert_agronomic"][0] == "Alta"

    # Maize: rain=19 (<20) -> ALERT
    row_maiz = dict(row_soja)
    row_maiz["lot_id"] = "m"
    row_maiz["crop"] = "maíz"
    row_maiz["rainfall_mm"] = 19
    df_maiz = build_fact_table([row_maiz], thresholds)
    assert df_maiz["alert_agronomic"][0] == "Alta"

    # Maize: rain=20 (==threshold) -> NO ALERT
    row_maiz["rainfall_mm"] = 20
    df_maiz2 = build_fact_table([row_maiz], thresholds)
    assert df_maiz2["alert_agronomic"][0] is None


if __name__ == "__main__":
    test_build_fact_table_with_alerts()
    test_expected_harvest_calculation()
    test_crop_specific_rainfall_threshold()
    print("All integration tests passed!")