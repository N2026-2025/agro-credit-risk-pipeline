# Agro Credit Risk Data Pipeline

Daily ETL pipeline that produces a Gold `fact_agro_credit_risk` table combining:
- **Satellite NDVI** from Planetary Computer Sentinel-2 L2A
- **Weather** (rainfall, temp) from Open-Meteo Archive
- **Credit risk** from BCRA Central de Deudores
- **Grain prices** from granos.ar

Architecture follows `diagram.svg` layering: Bronze → Silver → Gold.

## Quick Start

```bash
# 1. Clone & setup
git clone <this-repo>
cd Data\ engineer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp config/.env.example .env
# Edit .env with your MinIO/Postgres credentials

# 3. Start infra
docker compose up -d           # starts postgres, minio, airflow
# Wait for health: docker exec postgres pg_isready

# 4. Load seed data
python src/seed/cartera_seeder.py --rows 100 --output data/seed_cartera.csv

# 5. (Optional) Load CUITs into postgres via Airflow UI or psql
# psql postgres://postgres:postgres@localhost:5432/agro -c "\copy dim_cartera_clientes FROM data/seed_cartera.csv WITH (FORMAT csv)"

# 6. Trigger DAG
# Airflow UI: http://localhost:8080
# Or: docker exec airflow airflow dags trigger agro_credit_risk

# 7. Verify
# Check MinIO: mc mb agro-bronze / mc mb agro-silver
# Check table: docker exec postgres psql agro -c "SELECT count(*) FROM fact_agro_credit_risk;"
```

## Pipeline Overview

```
Sources (Planetary Computer, Open-Meteo, BCRA, granos.ar)
          │
          ▼
Bronze: MinIO buckets → bronze/{source}/{date}/raw JSON/GeoTIFF
          │
          ▼
Silver: Polars/GeoPandas transforms
        │   ├── ndvi.py  → lot-level median NDVI with SCL cloud mask
        │   ├── weather_join.py → weather per lot centroid
        │   ├── bcra_join.py → deuda + cheques per CUIT
        │   └── prices_join.py → precios pizarra + dolar oficial per crop
        ▼
Gold: fact_agro_credit_risk in Postgres/PostGIS
    │   ├── ndvi, ndvi_drop_pct vs hist avg
    │   ├── expected_harvest_usd = ha * yield_est * precio_usd_tn
    │   ├── debt_ratio = bcra_debt / expected_harvest
    │   ├── alert_agronomic: 'Alta' if ndvi_drop>20% AND low rain in critical month
    │   └── alert_default: 'Preventiva' if debt_ratio>70% OR cheques>0
          │
          ▼
Alerts → external notification (email/Slack/webhook) if any alert triggered
```

## Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Airflow + Postgres/PostGIS + MinIO services |
| `requirements.txt` | Python deps (polars, rasterio, geopandas, duckdb, pystac, etc.) |
| `config/thresholds.yml` | Editable thresholds: NDVI drop %, rainfall, base yields, debt ratio |
| `config/.env.example` | MinIO/Postgres/Airflow env vars |
| `src/seed/cartera_seeder.py` | Generates synthetic dim_cartera_clientes data |
| `src/dags/agro_credit_risk.py` | Airflow DAG: bronze → silver → gold |
| `tests/unit/test_ndvi.py` | NDVI + SCL cloud mask unit tests |
| `tests/unit/test_alerts.py` | Alert logic unit tests |

## Development

- Run tests: `python -m pytest tests/unit/ -v`
- Lint: `ruff check src/` (will be installed from requirements)
- Typecheck: `mypy src/` (will be installed from requirements)