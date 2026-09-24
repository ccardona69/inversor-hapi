"""Extracción y confirmación de informes sin red ni base de datos."""
import base64

import pytest

from app import ai_provider as AP
from app import fundsync as FS
from app.analysis import FUND_FIELDS


IMAGE = base64.b64encode(b"imagen de prueba").decode()


def test_analyze_only_extracts_visible_unscaled_fields(monkeypatch):
    calls = []

    def fake_request(instructions, user_text, **kwargs):
        calls.append((instructions, user_text, kwargs))
        return ({"data": {"revenue": 12.5, "fcf": 2, "shares_out": 30,
                          "eps": 1.25, "moat": "Patente visible", "extra": 900},
                 "report_asof": "2025-12-31", "period": "anual",
                 "unit": "millones USD", "shares_unit": "miles acciones",
                 "warnings": ["Verificar cifra"], "extra": "ignorado"}, "gpt-5.6-luna")

    monkeypatch.setattr(AP, "request", fake_request)
    client, env = object(), {"INVERSOR_AI_MODEL": "gpt-5.6-luna"}
    result = FS.analyze(IMAGE, "image/png", env=env, client=client)
    assert set(result["data"]) == {name for name, _ in FUND_FIELDS}
    assert result == {"data": {**dict.fromkeys(result["data"]), "revenue": 12.5,
                               "fcf": 2, "shares_out": 30, "eps": 1.25,
                               "moat": "Patente visible"},
                      "report_asof": "2025-12-31", "period": "anual",
                      "unit": "millones USD", "shares_unit": "miles acciones",
                      "warnings": ["Verificar cifra"], "model": "gpt-5.6-luna"}
    assert calls[0][2] == {"image_b64": IMAGE, "mime": "image/png", "env": env,
                           "client": client, "json_reply": True}
    assert "No calcules tasas de crecimiento" in calls[0][0]
    assert "Nunca presentes" in calls[0][0]
    assert "SIN escalar" in calls[0][0]


def test_analyze_never_fills_missing_or_invalid_numbers(monkeypatch):
    monkeypatch.setattr(AP, "request", lambda *a, **kw: (
        {"data": {"eps_fwd": None, "fcf": "no visible", "eps_growth_pct": True,
                  "debt": float("inf"), "revenue": "", "shares_out": 20,
                  "next_earnings_date": "2025-02-29"},
         "report_asof": "2025-02-29", "period": "trimestral",
         "unit": None, "shares_unit": None}, "luna"))
    result = FS.analyze(IMAGE, "image/jpeg")
    assert all(value is None for field, value in result["data"].items() if field != "shares_out")
    assert result["data"]["shares_out"] == 20
    assert result["report_asof"] is None
    assert result["period"] == "trimestral"
    assert result["unit"] is None and result["shares_unit"] is None
    assert any("acciones" in warning for warning in result["warnings"])
    with pytest.raises(FS.FundSyncError, match="trimestrales"):
        FS.confirmed_data(result["data"], "USD", "acciones", result["period"])


def test_analyze_reports_unknown_period_and_monetary_unit(monkeypatch):
    monkeypatch.setattr(AP, "request", lambda *a, **kw: (
        {"data": {"revenue": 3}, "period": None, "unit": None}, "luna"))
    result = FS.analyze(IMAGE, "image/webp")
    assert result["period"] is None and result["unit"] is None
    assert any("Período" in warning for warning in result["warnings"])
    assert any("monetaria" in warning for warning in result["warnings"])
    with pytest.raises(FS.FundSyncError, match="período"):
        FS.confirmed_data(result["data"], "USD", None, result["period"])


def test_analyze_handles_unexpected_metadata_types(monkeypatch):
    monkeypatch.setattr(AP, "request", lambda *a, **kw: (
        {"data": {"fcf": 1, "shares_out": 2}, "period": [],
         "unit": [], "shares_unit": {}}, "luna"))
    result = FS.analyze(IMAGE, "image/png")
    assert (result["period"], result["unit"], result["shares_unit"]) == (None, None, None)
    assert result["data"]["fcf"] == 1


def test_confirmed_data_scales_only_totals_and_shares():
    data = {"revenue": 12.5, "fcf": "2", "debt": 1, "cash": 0,
            "ebitda": 4, "buybacks": 0.25, "shares_out": 3,
            "eps": 1.5, "eps_fwd": 2, "gross_margin_pct": 30,
            "next_earnings_date": "2026-03-01", "key_risks": "  Competencia  ",
            "not_a_fund_field": 999}
    result = FS.confirmed_data(data, "millones USD", "miles acciones", "TTM")
    assert result == {"revenue": 12_500_000, "fcf": 2_000_000, "debt": 1_000_000,
                      "cash": 0, "ebitda": 4_000_000, "buybacks": 250_000,
                      "shares_out": 3_000, "eps": 1.5, "eps_fwd": 2,
                      "gross_margin_pct": 30, "next_earnings_date": "2026-03-01",
                      "key_risks": "Competencia"}
    assert data["fcf"] == "2"  # no muta los valores revisados


@pytest.mark.parametrize("key,unit,shares_unit", [
    ("revenue", None, None), ("fcf", None, None), ("debt", None, None),
    ("cash", None, None), ("ebitda", None, None), ("buybacks", None, None),
    ("shares_out", "USD", None),
])
def test_confirmed_data_requires_independent_units(key, unit, shares_unit):
    with pytest.raises(FS.FundSyncError, match="unidad"):
        FS.confirmed_data({key: 1}, unit, shares_unit, "anual")


@pytest.mark.parametrize("period", [None, "trimestral", "desconocido", "Anual"])
def test_confirmed_data_rejects_non_annual_periods(period):
    with pytest.raises(FS.FundSyncError, match="anual o TTM"):
        FS.confirmed_data({"eps": 2}, None, None, period)


def test_confirmed_data_whitelists_ignores_empty_and_rejects_nothing_visible():
    assert FS.confirmed_data({"eps": " 1.25 ", "moat": " ", "evil": 100},
                             None, None, "anual") == {"eps": 1.25}
    with pytest.raises(FS.FundSyncError, match="No hay datos"):
        FS.confirmed_data({"fcf": None, "moat": "  ", "evil": 100}, None, None, "TTM")
    with pytest.raises(FS.FundSyncError, match="No hay datos"):
        FS.confirmed_data({}, None, None, "anual")


@pytest.mark.parametrize("data", [
    {"eps": float("nan")}, {"eps": float("inf")}, {"eps": True},
    {"eps": "1,000"}, {"fcf": "1e309"},
    {"moat": "x" * (FS.MAX_TEXT + 1)},
    {"next_earnings_date": "2025-02-29"},
    {"next_earnings_date": "2025-2-1"},
])
def test_confirmed_data_rejects_invalid_values(data):
    with pytest.raises(FS.FundSyncError):
        FS.confirmed_data(data, "USD", "acciones", "anual")


def test_confirmed_data_rejects_invalid_units_and_scaled_overflow():
    with pytest.raises(FS.FundSyncError, match="monetaria"):
        FS.confirmed_data({"eps": 1}, "euros", None, "anual")
    with pytest.raises(FS.FundSyncError, match="acciones"):
        FS.confirmed_data({"eps": 1}, None, "inconocida", "anual")
    with pytest.raises(FS.FundSyncError, match="fuera de rango"):
        FS.confirmed_data({"fcf": 1e308}, "millones USD", None, "anual")
    with pytest.raises(FS.FundSyncError, match="anual o TTM"):
        FS.confirmed_data({"eps": 1}, None, None, [])
    with pytest.raises(FS.FundSyncError, match="monetaria"):
        FS.confirmed_data({"eps": 1}, [], None, "anual")
    with pytest.raises(FS.FundSyncError, match="acciones"):
        FS.confirmed_data({"eps": 1}, None, [], "anual")


def test_analyze_provider_error_and_image_validation(monkeypatch):
    def failing_request(*args, **kwargs):
        raise AP.AIProviderError("No se pudo contactar al servicio de IA")
    monkeypatch.setattr(AP, "request", failing_request)
    with pytest.raises(FS.FundSyncError, match="No se pudo contactar"):
        FS.analyze(IMAGE, "image/png")
    with pytest.raises(FS.FundSyncError, match="6 MB"):
        FS.analyze(base64.b64encode(b"x" * (AP.MAX_IMAGE_BYTES + 1)).decode(), "image/png")


def test_analyze_rejects_malformed_provider_reply(monkeypatch):
    monkeypatch.setattr(AP, "request", lambda *a, **kw: ({"data": []}, "luna"))
    with pytest.raises(FS.FundSyncError, match="interpretable"):
        FS.analyze(IMAGE, "image/png")
