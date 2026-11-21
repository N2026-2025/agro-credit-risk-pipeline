"""Configuration loader for thresholds and critical month settings."""

from pathlib import Path


def load_thresholds(path: str = "config/thresholds.yml") -> dict:
    """Load threshold values from config/thresholds.yml.

    Uses YAML when available, otherwise returns defaults.
    """
    p = Path(path)
    defaults = {
        "ndvi_drop_pct_threshold": 20,
        "rainfall_soja_mm": 15,
        "rainfall_maiz_mm": 20,
        "base_yield_soja_tn_ha": 3.0,
        "base_yield_maiz_tn_ha": 8.0,
        "base_yield_trigo_tn_ha": 4.5,
        "debt_ratio_threshold": 0.7,
        "rinde_clamp_min": 0.4,
        "rinde_clamp_max": 1.5,
        "critical_months_soja": [1, 2],
        "critical_months_maiz": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "critical_months_trigo": [1, 2, 3, 4, 5, 9, 10, 11, 12],
    }

    if not p.exists():
        return defaults

    try:
        import yaml

        with open(p) as f:
            loaded = yaml.safe_load(f) or {}
        defaults.update(loaded)
    except Exception:
        # Fall back to defaults if yaml unavailable or parse fails
        pass

    return defaults


if __name__ == "__main__":
    import json

    print(json.dumps(load_thresholds(), indent=2))