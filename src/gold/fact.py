"""Gold layer: Fact table `fact_agro_credit_risk`.

Computes:
1. ndvi_drop_pct vs historical avg
2. Expected harvest value USD: ha * rinde_est_tn_ha * precio_usd_tn
3. debt_ratio: bcra_debt_ars / expected_harvest_usd
4. Alerts: Agronomic (ndvi_drop>20 AND low rainfall in critical month) AND Default (debt_ratio>0.7 OR cheques>0)
"""

import logging

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_BASE_YIELD = {"soja": 3.0, "maíz": 8.0, "trigo": 4.5}
RINDING_CLAMP_MIN = 0.4
RINDING_CLAMP_MAX = 1.5


def compute_ndvi_drop(ndvi, ndvi_hist_avg):
    if ndvi_hist_avg is None or ndvi_hist_avg == -99 or ndvi_hist_avg == 0:
        return None
    if ndvi is None or ndvi == -99:
        return None
    return round(((ndvi_hist_avg - ndvi) / ndvi_hist_avg) * 100, 2)


def compute_rinde_est(ndvi, ndvi_hist_avg, crop, thresholds):
    base_yield = DEFAULT_BASE_YIELD.get(crop, DEFAULT_BASE_YIELD["soja"])
    if ndvi is None or ndvi == -99 or ndvi_hist_avg in (None, -99, 0):
        return None
    ratio = ndvi / ndvi_hist_avg
    ratio = max(RINDING_CLAMP_MIN, min(RINDING_CLAMP_MAX, ratio))
    rinde = base_yield * ratio
    return round(rinde, 2)


def build_fact_table(rows: list[dict], thresholds: dict) -> pl.DataFrame:
    """Assemble rows into fact_agro_credit_risk DataFrame.

    All derived columns (ndvi_drop_pct, expected_harvest_usd, debt_ratio,
    alert_agronomic, alert_default) are computed from input columns.

    Expected input row keys:
      lot_id, cuit, eval_date, ndvi, ndvi_hist_avg, crop, critical_month,
      rainfall_mm, hectareas, precio_usd_tn, bcra_debt_ars, cheques_rechazados
    """
    rows_out = []

    ndvi_drop_pct_threshold = thresholds.get("ndvi_drop_pct_threshold", 20)
    rainfall_soja_mm = thresholds.get("rainfall_soja_mm", 15)
    rainfall_maiz_mm = thresholds.get("rainfall_maiz_mm", 20)
    debt_ratio_threshold = thresholds.get("debt_ratio_threshold", 0.7)
    critical_months_soja = thresholds.get("critical_months_soja", [1, 2])

    for row in rows:
        ndvi = row.get("ndvi")
        ndvi_hist_avg = row.get("ndvi_hist_avg")
        crop = row.get("crop", "soja")
        critical_month = row.get("critical_month")
        rainfall_mm = row.get("rainfall_mm")
        hectareas = row.get("hectareas", 0)
        precio_usd_tn = row.get("precio_usd_tn", 0.0)
        bcra_debt_ars = row.get("bcra_debt_ars", 0.0)
        cheques_rechazados = row.get("cheques_rechazados", 0)

        # --- ndvi_drop_pct ---
        ndvi_drop_pct = compute_ndvi_drop(ndvi, ndvi_hist_avg)

        # --- rinde_est_tn_ha and expected_harvest_usd ---
        rinde_est = compute_rinde_est(ndvi, ndvi_hist_avg, crop, thresholds)
        expected_harvest_usd = round(hectareas * rinde_est * precio_usd_tn, 2) if rinde_est is not None else None

        # --- debt_ratio ---
        debt_ratio = None
        if expected_harvest_usd is not None and expected_harvest_usd > 0:
            debt_ratio = round(bcra_debt_ars / expected_harvest_usd, 4)

        # --- Alert agronomica ---
        alert_agronomic = None
        if ndvi_drop_pct is not None and ndvi_drop_pct > ndvi_drop_pct_threshold:
            rain_thresh = rainfall_maiz_mm if crop == "maíz" else rainfall_soja_mm
            if (
                critical_month in critical_months_soja
                and rainfall_mm is not None
                and rainfall_mm < rain_thresh
            ):
                alert_agronomic = "Alta"

        # --- Alert default ---
        alert_default = None
        if debt_ratio is not None and debt_ratio > debt_ratio_threshold:
            alert_default = "Preventiva"
        if cheques_rechazados > 0:
            alert_default = "Preventiva"

        # Build output row
        out = {
            "lot_id": row.get("lot_id"),
            "cuit": row.get("cuit"),
            "eval_date": row.get("eval_date"),
            "ndvi": ndvi,
            "ndvi_hist_avg": ndvi_hist_avg,
            "ndvi_drop_pct": ndvi_drop_pct,
            "crop": crop,
            "critical_month": critical_month,
            "rainfall_mm": rainfall_mm,
            "hectareas": hectareas,
            "precio_usd_tn": precio_usd_tn,
            "bcra_debt_ars": bcra_debt_ars,
            "cheques_rechazados": cheques_rechazados,
            "expected_harvest_usd": expected_harvest_usd,
            "debt_ratio": debt_ratio,
            "rinde_est_tn_ha": rinde_est,
            "alert_agronomic": alert_agronomic,
            "alert_default": alert_default,
        }
        rows_out.append(out)

    df = pl.DataFrame(rows_out)

    # Ensure numeric columns are Float64 (safe no-op if already correct)
    numeric_cols = ["ndvi", "ndvi_hist_avg", "ndvi_drop_pct", "rainfall_mm",
                    "expected_harvest_usd", "bcra_debt_ars", "debt_ratio"]
    for col in numeric_cols:
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Float64))

    # Cast integer columns
    if "cheques_rechazados" in df.columns:
        df = df.with_columns(pl.col("cheques_rechazados").cast(pl.Int64))

    return df


def run():
    pass