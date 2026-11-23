"""Unit tests for FX contracts."""
from src.schemas.fx_contracts import DefiLlamaStablecoinResponse, GDELTDocResponse, validate_fx_record


def test_defillama_contract_valid():
    model, err = validate_fx_record({
        "as_of_date": "2024-01-01", "asset": "USDC", "chain": "ethereum", "circulating_usd": 100.0
    }, DefiLlamaStablecoinResponse)
    assert err is None
    assert model.asset == "USDC"


def test_defillama_contract_invalid_negative():
    model, err = validate_fx_record({
        "as_of_date": "2024-01-01", "asset": "USDC", "chain": "ethereum", "circulating_usd": -1
    }, DefiLlamaStablecoinResponse)
    assert model is None
    assert err is not None


def test_gdelt_contract_allows_extra():
    model, err = validate_fx_record({
        "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T00:15:00Z",
        "country": "ARG", "query_hash": "abc", "unexpected": "ok"
    }, GDELTDocResponse)
    assert err is None
    assert model.country == "ARG"
