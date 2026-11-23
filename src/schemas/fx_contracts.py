"""Pydantic data contracts for FX & Treasury Risk Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ValidationError


class DefiLlamaStablecoinResponse(BaseModel):
    as_of_date: str
    asset: str
    chain: str
    circulating_usd: float = Field(ge=0)
    circulating_prev_usd: Optional[float] = Field(default=None, ge=0)
    source: str = "defillama_stablecoins"
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class DefiLlamaYieldResponse(BaseModel):
    as_of_date: str
    asset: str
    chain: str
    project: Optional[str] = None
    apy: float
    tvl_usd: float = Field(ge=0)
    source: str = "defillama_yields"
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class WorldBankIndicatorResponse(BaseModel):
    as_of_date: str
    country: str
    indicator: str
    value: Optional[float] = None
    period: Optional[str] = None
    source: str = "world_bank"
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class GDELTDocResponse(BaseModel):
    window_start: str
    window_end: str
    country: str
    query_hash: str
    url: Optional[str] = None
    seendate: Optional[str] = None
    title: Optional[str] = None
    tone: Optional[float] = None
    sourcecountry: Optional[str] = None
    source: str = "gdelt"
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class FREDSeriesResponse(BaseModel):
    as_of_date: str
    series_id: str
    value: Optional[float] = None
    source: str = "fred"
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class BCRAFXResponse(BaseModel):
    as_of_date: str
    series: str
    value: Optional[float] = None
    source: str = "bcra_fx"
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class SilverFXTreasuryRecord(BaseModel):
    as_of_date: str
    country: str
    currency: str
    asset: str
    chain: str
    fx_official: Optional[float] = Field(default=None, ge=0)
    fx_parallel: Optional[float] = Field(default=None, ge=0)
    fx_gap_pct: Optional[float] = None
    fx_vol_30d: Optional[float] = Field(default=None, ge=0)
    stablecoin_supply_usd: Optional[float] = Field(default=None, ge=0)
    stablecoin_net_flow_usd: Optional[float] = None
    stablecoin_net_flow_pct: Optional[float] = None
    stablecoin_apy: Optional[float] = None
    tbill_usd_rate: Optional[float] = None
    local_rate: Optional[float] = None
    opportunity_spread_bps: Optional[float] = None
    sovereign_risk_score: Optional[float] = Field(default=None, ge=0, le=1)
    reserves_change_pct: Optional[float] = None
    news_tension_score: Optional[float] = Field(default=None, ge=0, le=1)
    source: str = "fx_treasury_silver"


class GDELTWindowSilverRecord(BaseModel):
    country: str
    window_start: str
    window_end: str
    query_hash: str
    article_count: int = Field(ge=0)
    avg_tone: Optional[float] = None
    negative_share: Optional[float] = Field(default=None, ge=0, le=1)
    tension_score: float = Field(ge=0, le=1)
    top_keywords: list[str] = Field(default_factory=list)
    source: str = "gdelt_silver"


def validate_fx_record(raw: dict, schema_class: type[BaseModel]) -> tuple[Optional[BaseModel], Optional[list[str]]]:
    try:
        return schema_class(**raw), None
    except ValidationError as e:
        errs = []
        for err in e.errors():
            loc = err.get("loc", [])
            errs.append(f"{loc[0] if loc else 'root'}: {err['msg']}")
        return None, errs
