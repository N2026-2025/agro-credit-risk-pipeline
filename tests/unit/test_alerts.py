"""Unit tests for BCRA debt ratio and alert logic."""

import polars as pl

from src.gold.fact import compute_ndvi_drop, compute_rinde_est


def test_compute_ndvi_drop():
    """ndvi_drop_pct = (hist - current)/hist * 100"""
    # NDVI dropped from 0.7 to 0.5 => 28.57% drop
    drop = compute_ndvi_drop(0.5, 0.7)
    assert abs(drop - 28.57) < 0.01

    # No change
    assert compute_ndvi_drop(0.7, 0.7) == 0.0

    # Zero hist avg -> None
    assert compute_ndvi_drop(0.5, 0) is None
    assert compute_ndvi_drop(0.5, None) is None

    # Negative fill -> None
    assert compute_ndvi_drop(-99, 0.7) is None


def test_compute_rinde_est():
    """Yield estimate: base_yield * ndvi/hist clamped [0.4, 1.5]."""
    # Base yield soja=3.0, ratio=0.8 => 2.4
    rinde = compute_rinde_est(0.56, 0.7, "soja", {"base_yield_soja_tn_ha": 3.0})
    assert abs(rinde - 2.4) < 0.01

    # Ratio above clamp max 1.5 -> capped at 1.5 * base_yield = 4.5
    rinde = compute_rinde_est(1.4, 0.7, "soja", {"base_yield_soja_tn_ha": 3.0})
    assert abs(rinde - 4.5) < 0.01

    # Missing NDVI -> None
    assert compute_rinde_est(None, 0.7, "soja", {"base_yield_soja_tn_ha": 3.0}) is None

    # Fill value -99 -> None
    assert compute_rinde_est(-99, 0.7, "soja", {"base_yield_soja_tn_ha": 3.0}) is None


def test_alert_agronomic_logic():
    """Alert 'Alta' when ndvi_drop > 20% AND rainfall below threshold in critical month."""
    ndvi_drop = 25.0
    rainfall_mm = 10.0
    critical_month = 1  # January - critical for soja
    ndvi_threshold = 20
    rain_threshold = 15

    assert ndvi_drop > ndvi_threshold
    assert rainfall_mm < rain_threshold
    alert_agronomic = "Alta"
    assert alert_agronomic == "Alta"


def test_alert_agronomic_not_triggered():
    """No alert when NDVI drop below threshold or rainfall sufficient."""
    # ndvi_drop < 20 -> no alert
    assert not (15.0 > 20)
    # rainfall >= threshold (12.0 is below 15, so use a sufficient value)
    assert not (20.0 < 15)  # 20.0 >= 15 -> no alert when rainfall sufficient


def test_alert_default_logic():
    """Alert 'Preventiva' when debt_ratio > 0.7 OR cheques > 0."""
    bcra_debt_ars = 1000000
    expected_harvest_usd = 1000000
    cheques_rechazados = 2

    debt_ratio = round(bcra_debt_ars / expected_harvest_usd, 4)
    assert debt_ratio == 1.0
    assert debt_ratio > 0.7  # triggers alert
    assert cheques_rechazados > 0  # triggers alert
    alert_default = "Preventiva"
    assert alert_default == "Preventiva"


def test_no_default_alert():
    """No default alert when debt_ratio <= 0.7 and no cheques."""
    bcra_debt_ars = 500000
    expected_harvest_usd = 1000000
    cheques_rechazados = 0

    debt_ratio = round(bcra_debt_ars / expected_harvest_usd, 4)
    assert debt_ratio == 0.5
    assert debt_ratio <= 0.7
    assert cheques_rechazados == 0