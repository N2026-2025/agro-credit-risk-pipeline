"""Gold layer: Fact table `fact_agro_credit_risk`.

Computes:
1. ndvi_drop_pct vs historical avg
2. Expected harvest value USD: ha * yield_est_tn_ha * precio_usd_tn
3. debt_ratio: bcra_debt_ars / expected_harvest_usd
4. Alerts: Agronomic (ndvi_drop>20 AND low rainfall in critical month) AND Default (debt_ratio>0.7 OR cheques>0)
"""

import logging
from typing import Literal

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_BASE_YIELD = {"soja": 3.0, "maíz": 8.0, "trigo": 4.5}
RINDING_CLAMP_MIN = 0.4
RINDING_CLAMP_MAX = 1.5


def compute_ndvi_drop(ndvi: float, ndvi_hist_avg: float) -> float:
    if ndvi_hist_avg is None or ndvi_hist_avg == -99 or ndvi_hist_avg == 0:
        return None
    if ndvi is None or ndvi == -99:
        return None
    return round(((ndvi_hist_avg - ndvi) / ndvi_hist_avg) * 100, 2)


def compute_rinde_est(ndvi: float, ndvi_hist_avg: float, crop: str, thresholds: dict) -> float:
    base_yield = DEFAULT_BASE_YIELD.get(crop, DEFAULT_BASE_YIELD["soja"])
    if ndvi is None or ndvi == -99 or ndvi_hist_avg in (None, -99, 0):
        return None
    ratio = ndvi / ndvi_hist_avg
    # Clamp ratio to [rinde_clamp_min, rinde_clamp_max]
    ratio = max(RINDING_CLAMP_MIN, min(RINDING_CLAMP_MAX, ratio))
    rinde = base_yield * ratio
    return round(rinde, 2)


def build_fact_table(
    rows: list[dict],
    thresholds: dict,
) -> pl.DataFrame:
    """Assemble rows into fact_agro_credit_risk DataFrame with all computed columns."""
    alert_agronomic_values = []
    alert_default_values = []

    for row in rows:
        ndvi_drop_pct = row.get("ndvi_drop_pct")
        rainfall_mm = row.get("rainfall_mm")
        critical_month = row.get("critical_month")
        alert_agronomic = None

        if ndvi_drop_pct is not None and ndvi_drop_pct > thresholds.get("ndvi_drop_pct_threshold", 20):
            rain_thresh = thresholds.get("rainfall_maiz_mm", 20) if row.get("crop") == "maíz" else thresholds.get("rainfall_soja_mm", 15)
            if critical_month in (thresholds.get("critical_months_soja", [1, 2]) or [1, 2]) and rainfall_mm is not None and rainfall_mm < rain_thresh:
                alert_agronomic = "Alta"

        expected_harvest_usd = row.get("expected_harvest_usd")
        debt_ratio = None
        if expected_harvest_usd and expected_harvest_usd > 0:
            debt_ratio = round(row.get("bcra_debt_ars", 0) / expected_harvest_usd, 4)

        alert_default = None
        if debt_ratio is not None and debt_ratio > thresholds.get("debt_ratio_threshold", 0.7):
            alert_default = "Preventiva"
        if row.get("cheques_rechazados", 0) > 0:
            alert_default = "Preventiva"

        alert_agronomic_values.append(alert_agronomic)
        alert_default_values.append(alert_default)

    df = pl.DataFrame(rows).with_columns(
        pl.col("ndvi_drop_pct").cast(pl.Float64).alias("ndvi_drop_pct"),
        pl.col("expected_harvest_usd").cast(pl.Float64).alias("expected_harvest_usd"),
        pl.col("debt_ratio").cast(pl.Float64).alias("debt_ratio"),
    )

    df = df.with_columns(
        pl.lit(alert_agronomic_values).list().join(" ").alias("alert_agronomic_list").cast(pl.String),
    )
    df = df.with_columns(pl.col("alert_agronomic_list").str.replace_all(r"\[|\]", "").alias("alert_agronomic"))

    df = df.with_columns(
        pl.lit(alert_default_values).list().join(" ").alias("alert_default_list").cast(pl.String),
    )
    df = df.with_columns(pl.col("alert_default_list").str.replace_all(r"\[|\]", "").alias("alert_default"))

    # Normalize to clean strings
    df = df.with_columns(
        pl.col("alert_agronomic").str.replace_all("null", "None").str.strip().alias("alert_agronomic"),
        pl.col("alert_default").str.replace_all("null", "None").str.strip().alias("alert_default"),
    )

    return df


if __name__ == "__main__":
    logger.info("Gold layer module loaded. Use via Airflow DAG to assemble full fact table.")


def run():
    # Placeholder for full pipeline integration
    pass
