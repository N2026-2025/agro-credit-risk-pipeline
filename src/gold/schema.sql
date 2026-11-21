-- PostgreSQL / PostGIS schema for Agro Credit Risk pipeline
-- Run with: psql postgres://postgres:postgres@localhost:5432/agro -f src/gold/schema.sql

-- Extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1) dim_cartera_clientes: master table of 50-200 Santa Fe ag producers + lot polygons
CREATE TABLE IF NOT EXISTS dim_cartera_clientes (
    cuit            TEXT PRIMARY KEY,
    nombre_razon_social TEXT NOT NULL,
    rubro           TEXT,
    hectareas_totales NUMERIC(10,2),
    crop            TEXT CHECK (crop IN ('soja','maíz','trigo')),
    geometry        geometry(Polygon, 4326),  -- lot polygon GeoJSON
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_cartera_cuit ON dim_cartera_clientes(cuit);
CREATE INDEX IF NOT EXISTS idx_dim_cartera_geom ON dim_cartera_clientes USING GIST (geometry);

-- 2) fact_agro_credit_risk: daily gold fact table
CREATE TABLE IF NOT EXISTS fact_agro_credit_risk (
    lot_id              TEXT NOT NULL,
    cuit                TEXT NOT NULL,
    eval_date           DATE NOT NULL,
    ndvi                DOUBLE PRECISION,
    ndvi_hist_avg       DOUBLE PRECISION,
    ndvi_drop_pct       DOUBLE PRECISION,
    rainfall_mm         DOUBLE PRECISION,
    alert_agronomic     TEXT CHECK (alert_agronomic IS NULL OR alert_agronomic IN ('Alta',)),
    hectareas           DOUBLE PRECISION,
    rinde_est_tn_ha     DOUBLE PRECISION,
    precio_usd_tn       DOUBLE PRECISION,
    expected_harvest_usd DOUBLE PRECISION,
    bcra_debt_ars       DOUBLE PRECISION,
    debt_ratio          DOUBLE PRECISION,
    cheques_rechazados  INTEGER DEFAULT 0,
    alert_default       TEXT CHECK (alert_default IS NULL OR alert_default IN ('Preventiva',)),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (lot_id, cuit, eval_date)
);

CREATE INDEX IF NOT EXISTS idx_fact_eval_date ON fact_agro_credit_risk(eval_date);
CREATE INDEX IF NOT EXISTS idx_fact_cuit ON fact_agro_credit_risk(cuit);
CREATE INDEX IF NOT EXISTS idx_fact_alerts ON fact_agro_credit_risk(lot_id, eval_date)
    WHERE alert_agronomic = 'Alta' OR alert_default = 'Preventiva';

-- 3) Alert view: quick lookup of active alerts
CREATE OR REPLACE VIEW vw_alertas_activas AS
SELECT lot_id, cuit, eval_date, ndvi_drop_pct, rainfall_mm,
       alert_agronomic, expected_harvest_usd, bcra_debt_ars, debt_ratio,
       cheques_rechazados, alert_default
FROM fact_agro_credit_risk
WHERE alert_agronomic = 'Alta' OR alert_default = 'Preventiva';

-- Grant (optional, adjust roles as needed)
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
