"""Gold: FX & Treasury risk fact builder with alerts and formal decisions."""
from __future__ import annotations

import json

import polars as pl


def _bool(v: bool) -> bool:
    return bool(v)


def build_fx_treasury_fact(rows: list[dict], thresholds: dict) -> pl.DataFrame:
    alerts_cfg = thresholds.get("alerts", {})
    rules = thresholds.get("decision_rules", {})
    ver = str(rules.get("version", "1.0"))
    out = []
    for r in rows:
        fx_gap = r.get("fx_gap_pct")
        fx_vol = r.get("fx_vol_30d")
        flow_pct = r.get("stablecoin_net_flow_pct")
        flow_usd = r.get("stablecoin_net_flow_usd")
        reserves_chg = r.get("reserves_change_pct")
        tension = r.get("news_tension_score")
        apy = r.get("stablecoin_apy")
        tbill = r.get("tbill_usd_rate")
        spread_bps = r.get("opportunity_spread_bps")
        sov = r.get("sovereign_risk_score")

        alert_fx_gap = fx_gap is not None and fx_gap >= alerts_cfg.get("fx_gap_pct_threshold", 20.0)
        alert_stablecoin_outflow = flow_pct is not None and flow_pct <= alerts_cfg.get("stablecoin_outflow_pct_threshold", -2.0)
        alert_reserves_drop = reserves_chg is not None and reserves_chg <= alerts_cfg.get("reserves_drop_pct_threshold", -5.0)
        alert_news_tension = tension is not None and tension >= alerts_cfg.get("news_tension_threshold", 0.7)
        alert_yield_anomaly = spread_bps is not None and abs(spread_bps) >= alerts_cfg.get("yield_anomaly_bps_threshold", 300)

        decision_action = "HOLD_LOCAL"
        decision_reason = "default: no formal rule triggered"
        decision_confidence = 0.55

        red = rules.get("reduce_exposure", {})
        hed = rules.get("hedge_fx", {})
        stc = rules.get("move_to_stablecoin", {})
        tbr = rules.get("move_to_tbill", {})

        if (
            tension is not None and tension >= red.get("news_tension_min", 0.7)
            and fx_gap is not None and fx_gap >= red.get("fx_gap_pct_min", 20.0)
            and (flow_usd is not None and flow_usd <= red.get("stablecoin_net_flow_max", 0.0))
        ):
            decision_action = "REDUCE_EXPOSURE"
            decision_reason = "high news tension + fx gap + stablecoin outflow"
            decision_confidence = 0.85
        elif (
            (fx_vol is not None and fx_vol >= hed.get("fx_vol_30d_min", 0.05))
            or (fx_gap is not None and fx_gap >= hed.get("fx_gap_pct_min", 15.0))
        ):
            decision_action = "HEDGE_FX"
            decision_reason = "fx volatility/gap above hedge threshold"
            decision_confidence = 0.75
        elif (
            spread_bps is not None and spread_bps >= stc.get("opportunity_spread_bps_min", 150)
            and not (flow_pct is not None and flow_pct <= stc.get("max_stablecoin_outflow_pct", -2.0))
            and (sov is None or sov <= stc.get("sovereign_risk_max", 0.7))
        ):
            decision_action = "MOVE_TO_STABLECOIN"
            decision_reason = "positive stablecoin opportunity spread with controlled risk"
            decision_confidence = 0.7
        elif (
            tbill is not None and apy is not None
            and tbr.get("policy_allows_tbill", True)
            and ((float(tbill) - float(apy)) * 100) >= tbr.get("tbill_over_stablecoin_apy_bps_min", 100)
        ):
            decision_action = "MOVE_TO_TBILL"
            decision_reason = "tbill yield exceeds stablecoin apy by policy margin"
            decision_confidence = 0.72

        row = dict(r)
        row.update({
            "alert_fx_gap": _bool(alert_fx_gap),
            "alert_stablecoin_outflow": _bool(alert_stablecoin_outflow),
            "alert_reserves_drop": _bool(alert_reserves_drop),
            "alert_news_tension": _bool(alert_news_tension),
            "alert_yield_anomaly": _bool(alert_yield_anomaly),
            "decision_action": decision_action,
            "decision_reason": decision_reason,
            "decision_confidence": decision_confidence,
            "decision_rule_version": ver,
            "decision_inputs_json": json.dumps({
                "fx_gap_pct": fx_gap, "fx_vol_30d": fx_vol, "stablecoin_net_flow_pct": flow_pct,
                "stablecoin_net_flow_usd": flow_usd, "reserves_change_pct": reserves_chg,
                "news_tension_score": tension, "stablecoin_apy": apy, "tbill_usd_rate": tbill,
                "opportunity_spread_bps": spread_bps, "sovereign_risk_score": sov,
            }),
        })
        out.append(row)
    return pl.DataFrame(out)
