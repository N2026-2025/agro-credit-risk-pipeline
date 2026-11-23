"""
Data contracts (Pydantic schemas) for all API sources and Silver layer outputs.

If any upstream API changes a field name or type, validation fails here and
the offending record is routed to the quarantine table instead of corrupting
Silver/Gold.
"""

from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, validator, ValidationError


# ---------------------------------------------------------------------------
# Bronze-layer source schemas (strict validation of raw API responses)
# ---------------------------------------------------------------------------

class BCRAResponse(BaseModel):
    """Bronze schema for BCRA Central de Deudores API response.
    
    Allows extra fields to tolerate API schema drift; required fields are validated.
    """

    cuit: str = Field(..., description="CUIT del productor")
    eval_date: str = Field(..., description="Fecha de evaluación (YYYY-MM-DD)")
    # Key fields we care about (optional in raw API)
    deuda_total_ars: Optional[float] = Field(
        default=0.0, description="Deuda total en ARS"
    )
    situacion_risk: Optional[int] = Field(
        default=0, description="Situación crediticia (1-5)"
    )
    cheques_sin_fondos: Optional[int] = Field(
        default=0, description="Cheques rechazados"
    )
    source: str = Field(default="bcra")
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"  # Allow extra fields from raw API


class GranosPriceResponse(BaseModel):
    """Bronze schema for granos.ar / MAGyP prices API response.
    
    Allows extra fields to tolerate API schema drift.
    """

    eval_date: str = Field(..., description="Fecha de los precios (YYYY-MM-DD)")
    soja_ars_tn: Optional[float] = Field(default=0.0)
    maiz_ars_tn: Optional[float] = Field(default=0.0)
    trigo_ars_tn: Optional[float] = Field(default=0.0)
    dolar_oficial: Optional[float] = Field(default=0.0)
    soja_usd_tn: Optional[float] = Field(default=None)
    maiz_usd_tn: Optional[float] = Field(default=None)
    trigo_usd_tn: Optional[float] = Field(default=None)
    source: str = Field(default="granos")
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class PlanetarySceneResponse(BaseModel):
    """Bronze schema for Planetary Computer STAC item metadata.
    
    Allows extra fields to tolerate API schema drift.
    """

    lot_id: str = Field(..., description="Identificador del lote agrícola")
    eval_date: str = Field(..., description="Fecha de evaluación (YYYY-MM-DD)")
    stac_item_id: str = Field(..., description="ID del ítem STAC de Sentinel-2")
    cloud_cover_pct: Optional[float] = Field(default=0.0)
    bands_tif_path: Optional[str] = Field(default=None)
    acquisition_date: Optional[str] = Field(default=None)
    source: str = Field(default="planetary_computer")
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"


class WeatherResponse(BaseModel):
    """Bronze schema for Open-Meteo archive API response.
    
    Allows extra fields to tolerate API schema drift.
    """

    lot_id: str = Field(..., description="Identificador del lote agrícola")
    lat: float = Field(..., description="Latitud del centroide del lote")
    lon: float = Field(..., description="Longitud del centroide del lote")
    eval_date: str = Field(..., description="Fecha de evaluación (YYYY-MM-DD)")
    rainfall_mm: Optional[float] = Field(default=None)
    temp_max_c: Optional[float] = Field(default=None)
    temp_min_c: Optional[float] = Field(default=None)
    source: str = Field(default="open_meteo")
    ingested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"
# Silver-layer output schemas (validated before writing to Parquet)
# ---------------------------------------------------------------------------

class SilverBCRARecord(BaseModel):
    """Validated Silver record for BCRA risk fields."""

    cuit: str
    eval_date: str
    deuda_total_ars: float = Field(ge=0, description="No puede ser negativa")
    situacion_risk: int = Field(ge=1, le=5, description="Rango 1-5")
    cheques_sin_fondos: int = Field(ge=0, description="No puede ser negativo")
    source: str = "bcra"
    tokenized_cuit: str = ""


class SilverWeatherRecord(BaseModel):
    """Validated Silver record for weather data."""

    lot_id: str
    eval_date: str
    rainfall_mm: Optional[float] = Field(
        default=None, ge=0, description="mm de lluvia, no negativo"
    )
    temp_max_c: Optional[float]
    temp_min_c: Optional[float]
    source: str = "open_meteo"


class SilverPricesRecord(BaseModel):
    """Validated Silver record for grain prices."""

    lot_id: str
    cuit: str
    crop: str = Field(
        ..., pattern=r"^(soja|maíz|trigo)$", description="Cultivo válido"
    )
    eval_date: str
    precio_ars_tn: float = Field(ge=0)
    precio_usd_tn: Optional[float] = Field(default=None, ge=0)
    dolar_oficial: float = Field(ge=0)
    source: str = "granos"
    tokenized_lot_id: str = ""


class SilverNDVIRecord(BaseModel):
    """Validated Silver record for NDVI values."""

    lot_id: str
    eval_date: str
    ndvi_median: float = Field(ge=-1.0, le=1.0, description="NDVI en [-1, 1]")
    ndvi_count: int = Field(ge=0, description="Cantidad de píxeles válidos")
    source: str = "planetary_computer"


# ---------------------------------------------------------------------------
# Quarantine / Dead Letter Queue record
# ---------------------------------------------------------------------------

class QuarantineRecord(BaseModel):
    """Record placed in quarantine when schema validation fails."""

    source_system: str = Field(..., description="bcra | granos | planetary | weather")
    raw_payload: dict = Field(..., description="JSON original recibido de la API")
    validation_errors: list[str] = Field(
        ..., description="Lista de errores de validación de Pydantic"
    )
    eval_date: str
    lot_id_or_cuit: Optional[str] = Field(
        default=None, description="Identificador del lote o CUIT si se conoce"
    )
    quarantined_at: datetime = Field(default_factory=datetime.utcnow)
    pipeline_run_id: Optional[str] = Field(
        default=None, description="ID de ejecución del DAG de Airflow"
    )
    schema_version: str = Field(default="1.0", description="Versión del contrato violado")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_against_schema(
    raw: dict, schema_class: type[BaseModel]
) -> tuple[Optional[BaseModel], Optional[list[str]]]:
    """
    Validate a raw dict against a Pydantic schema.

    Returns:
        (validated_model, None) on success
        (None, [error_messages]) on failure
    """
    try:
        model = schema_class(**raw)
        return model, None
    except ValidationError as e:
        errors = [f"{err['loc'][0] if err['loc'] else 'root'}: {err['msg']}" for err in e.errors()]
        return None, errors


def extract_validation_errors(errors: list[str]) -> list[str]:
    """Return a clean list of error strings from Pydantic validation."""
    return errors