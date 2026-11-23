-- FX & Treasury Risk Engine schema
CREATE TABLE IF NOT EXISTS fact_gdelt_tension_15m (
    country TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    query_hash TEXT NOT NULL,
    article_count INTEGER NOT NULL DEFAULT 0,
    avg_tone DOUBLE PRECISION,
    negative_share DOUBLE PRECISION,
    tension_score DOUBLE PRECISION,
    top_keywords JSONB,
    raw_object_key TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (country, window_start, query_hash)
);

CREATE INDEX IF NOT EXISTS idx_gdelt_15m_window ON fact_gdelt_tension_15m(window_start);
CREATE INDEX IF NOT EXISTS idx_gdelt_15m_country ON fact_gdelt_tension_15m(country);

CREATE TABLE IF NOT EXISTS fact_treasury_risk_daily (
    as_of_date DATE NOT NULL,
    country TEXT NOT NULL,
    currency TEXT NOT NULL,
    asset TEXT NOT NULL,
    chain TEXT NOT NULL,
    fx_official DOUBLE PRECISION,
    fx_parallel DOUBLE PRECISION,
    fx_gap_pct DOUBLE PRECISION,
    fx_vol_30d DOUBLE PRECISION,
    stablecoin_supply_usd DOUBLE PRECISION,
    stablecoin_net_flow_usd DOUBLE PRECISION,
    stablecoin_net_flow_pct DOUBLE PRECISION,
    stablecoin_apy DOUBLE PRECISION,
    tbill_usd_rate DOUBLE PRECISION,
    local_rate DOUBLE PRECISION,
    opportunity_spread_bps DOUBLE PRECISION,
    sovereign_risk_score DOUBLE PRECISION,
    reserves_change_pct DOUBLE PRECISION,
    news_tension_score DOUBLE PRECISION,
    alert_fx_gap BOOLEAN DEFAULT FALSE,
    alert_stablecoin_outflow BOOLEAN DEFAULT FALSE,
    alert_reserves_drop BOOLEAN DEFAULT FALSE,
    alert_news_tension BOOLEAN DEFAULT FALSE,
    alert_yield_anomaly BOOLEAN DEFAULT FALSE,
    decision_action TEXT,
    decision_reason TEXT,
    decision_confidence DOUBLE PRECISION,
    decision_rule_version TEXT,
    decision_inputs_json JSONB,
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (as_of_date, country, currency, asset, chain)
);

CREATE INDEX IF NOT EXISTS idx_fx_daily_date ON fact_treasury_risk_daily(as_of_date);
CREATE INDEX IF NOT EXISTS idx_fx_daily_country ON fact_treasury_risk_daily(country);
CREATE INDEX IF NOT EXISTS idx_fx_daily_decision ON fact_treasury_risk_daily(decision_action);
CREATE INDEX IF NOT EXISTS idx_fx_daily_alerts ON fact_treasury_risk_daily(as_of_date)
    WHERE alert_fx_gap OR alert_stablecoin_outflow OR alert_reserves_drop OR alert_news_tension OR alert_yield_anomaly;

CREATE OR REPLACE VIEW vw_fx_treasury_alerts AS
SELECT as_of_date, country, currency, asset, chain,
       fx_gap_pct, fx_vol_30d, stablecoin_net_flow_pct, reserves_change_pct, news_tension_score,
       alert_fx_gap, alert_stablecoin_outflow, alert_reserves_drop, alert_news_tension, alert_yield_anomaly,
       decision_action, decision_reason, decision_confidence
FROM fact_treasury_risk_daily
WHERE alert_fx_gap OR alert_stablecoin_outflow OR alert_reserves_drop OR alert_news_tension OR alert_yield_anomaly;

CREATE OR REPLACE VIEW vw_fx_treasury_decisions AS
SELECT as_of_date, country, currency, asset, chain, decision_action, decision_reason,
       decision_confidence, decision_rule_version, decision_inputs_json, processed_at
FROM fact_treasury_risk_daily;
