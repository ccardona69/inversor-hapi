"""Fundamentales SEC EDGAR: extracción pura del 10-K, red y endpoint.

La red nunca se toca: extract_fundamentals es pura y fetch_fundamentals recibe
un cliente falso con .get(url, headers=...). Las pruebas de endpoint usan una
BD aislada con tmp_path.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import db as D
from app import secdata as SEC
from app.main import app

ACC = "0000-00-000010"      # accn del 10-K más reciente
OTHER = "0000-00-000001"    # otra presentación: sus valores deben ignorarse
AMD = "0000-00-000011"      # accn de un 10-K/A posterior: debe ignorarse


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "isolated.db"))
    D.init_db()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_cache():
    SEC._clear_cache()
    yield
    SEC._clear_cache()


def fact(val, end, start=None, accn=ACC, form="10-K", filed="2026-02-01"):
    h = {"val": val, "end": end, "accn": accn, "form": form, "filed": filed,
         "fy": 2025, "fp": "FY"}
    if start is not None:
        h["start"] = start
    return h


def base_facts(**extra_tags):
    """companyfacts sintético que ejercita todas las reglas de extracción."""
    tags = {
        # Ingresos por el SEGUNDO tag (Revenues no existe en esta empresa)
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            fact(110_000, "2025-12-31", start="2025-01-01"),   # anual actual
            fact(100_000, "2024-12-31", start="2024-01-01"),   # previo, mismo accn
            fact(999_999, "2024-12-31", start="2024-01-01",    # otro accn: ignorar
                 accn=OTHER, filed="2025-02-01"),
            fact(30_000, "2025-12-31", start="2025-10-01"),    # trimestral ~91 días
            fact(115_000, "2025-12-31", start="2025-01-01",    # 10-K/A posterior: ignorar
                 accn=AMD, form="10-K/A", filed="2026-03-15"),
        ]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [
            fact(5.0, "2025-12-31", start="2025-01-01"),
            fact(4.0, "2024-12-31", start="2024-01-01"),
        ]}},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
            fact(20_000, "2025-12-31", start="2025-01-01"),
        ]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
            fact(50_000, "2025-12-31", start="2025-01-01"),
        ]}},
        # Capex por el SEGUNDO tag (PaymentsToAcquirePropertyPlantAndEquipment ausente)
        "PaymentsToAcquireProductiveAssets": {"units": {"USD": [
            fact(10_000, "2025-12-31", start="2025-01-01"),
        ]}},
        "OperatingIncomeLoss": {"units": {"USD": [
            fact(22_000, "2025-12-31", start="2025-01-01"),
        ]}},
        "GrossProfit": {"units": {"USD": [
            fact(55_000, "2025-12-31", start="2025-01-01"),
        ]}},
        "Depreciation": {"units": {"USD": [
            fact(3_000, "2025-12-31", start="2025-01-01"),
        ]}},
        "PaymentsForRepurchaseOfCommonStock": {"units": {"USD": [
            fact(5_000, "2025-12-31", start="2025-01-01"),
        ]}},
        "CashCashEquivalentsAndShortTermInvestments": {"units": {"USD": [
            fact(80_000, "2025-12-31"),   # instantáneo al cierre del ejercicio
        ]}},
        "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities": {"units": {"USD": [
            fact(30_000, "2025-12-31"),
        ]}},
        "CommercialPaper": {"units": {"USD": [fact(2_000, "2025-12-31")]}},
        "OtherShortTermBorrowings": {"units": {"USD": [fact(1_000, "2025-12-31")]}},
    }
    tags.update(extra_tags)
    return {"cik": 1, "entityName": "Prueba SA", "facts": {"us-gaap": tags}}


def test_extract_base_cases():
    r = SEC.extract_fundamentals(base_facts())
    assert r["accn"] == ACC and r["filed"] == "2026-02-01"  # no el del 10-K/A
    assert r["period_end"] == "2025-12-31"
    d = r["data"]
    assert d["revenue"] == 110_000 and d["revenue_growth_pct"] == 10.0
    assert d["eps"] == 5.0 and d["eps_growth_pct"] == 25.0
    assert d["shares_out"] == 20_000
    assert d["fcf"] == 40_000            # 50 000 − capex por ProductiveAssets
    assert d["op_margin_pct"] == 20.0
    assert d["gross_margin_pct"] == 50.0
    assert d["ebitda"] == 25_000         # 22 000 + Depreciation
    assert d["buybacks"] == 5_000
    assert d["cash"] == 80_000           # tag combinado
    assert d["debt"] == 33_000           # LTD(incl. current) + CP + OtherShortTermBorrowings
    assert "EPS estimado próximo año" in r["missing"]   # la SEC no provee eps_fwd
    assert "detalle" in r and r["detalle"]["debt"].startswith(
        "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities")


def test_extract_cash_fallback_sum():
    facts = base_facts()
    del facts["facts"]["us-gaap"]["CashCashEquivalentsAndShortTermInvestments"]
    facts["facts"]["us-gaap"]["CashAndCashEquivalentsAtCarryingValue"] = {
        "units": {"USD": [fact(60_000, "2025-12-31")]}}
    facts["facts"]["us-gaap"]["ShortTermInvestments"] = {
        "units": {"USD": [fact(20_000, "2025-12-31")]}}
    r = SEC.extract_fundamentals(facts)
    assert r["data"]["cash"] == 80_000


def test_extract_debt_missing_without_long_term_tag():
    facts = base_facts()
    del facts["facts"]["us-gaap"]["LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"]
    r = SEC.extract_fundamentals(facts)
    assert "debt" not in r["data"]       # hay papel comercial, pero sin LTD no se estima


def test_extract_annual_end_off_fy_counts_as_missing():
    facts = base_facts()
    facts["facts"]["us-gaap"]["EarningsPerShareDiluted"] = {"units": {"USD/shares": [
        fact(5.0, "2025-06-30", start="2024-07-01"),   # end distinto de FY_END
    ]}}
    r = SEC.extract_fundamentals(facts)
    assert "eps" not in r["data"]


def test_extract_no_10k_404():
    facts = base_facts()
    for tag in facts["facts"]["us-gaap"].values():
        for unit_facts in tag["units"].values():
            for h in unit_facts:
                h["form"] = "10-Q"
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.extract_fundamentals(facts)
    assert ei.value.status == 404
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.extract_fundamentals({"facts": {"us-gaap": {}}})
    assert ei.value.status == 404
    # JSON sin us-gaap → 404
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.extract_fundamentals({"facts": {}})
    assert ei.value.status == 404


# ---------- fetch_fundamentals con cliente falso ----------

class _Resp:
    def __init__(self, status, payload=None, exc=None):
        self.status_code, self._payload, self._exc = status, payload, exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._payload


class SecFake:
    """Cliente httpx falso para la SEC: .get(url, headers=...) con registro."""

    def __init__(self, facts_resp=None, tickers=None):
        self._tickers = tickers if tickers is not None else {
            "0": {"cik_str": 1234, "ticker": "ABC", "title": "Prueba SA"}}
        self._facts = facts_resp if facts_resp is not None else _Resp(200, base_facts())
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append((url, headers))
        if "company_tickers" in url:
            return _Resp(200, self._tickers)
        return self._facts


def test_fetch_ok_and_headers():
    client = SecFake()
    r = SEC.fetch_fundamentals("abc", client=client)
    assert r["data"]["revenue"] == 110_000 and r["accn"] == ACC
    assert client.calls[0][1]["User-Agent"]          # siempre con User-Agent


def test_fetch_ticker_not_found_404():
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.fetch_fundamentals("VOO", client=SecFake())
    assert ei.value.status == 404 and "ETF" in ei.value.detail


def test_cik_override_beats_ticker_map():
    """La tabla de la SEC apunta XOM a un holding sin 10-K; el override gana."""
    client = SecFake(tickers={"0": {"cik_str": 2115436, "ticker": "XOM",
                                    "title": "ExxonMobil Holdings Corp"}})
    assert SEC.cik_for("XOM", client=client) == 34088


def test_fetch_facts_404_and_500():
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.fetch_fundamentals("ABC", client=SecFake(facts_resp=_Resp(404)))
    assert ei.value.status == 404 and "10-K" in ei.value.detail
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.fetch_fundamentals("ABC", client=SecFake(facts_resp=_Resp(500)))
    assert ei.value.status == 502


def test_fetch_unreadable_json_502():
    bad = _Resp(200, exc=ValueError("json roto"))
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.fetch_fundamentals("ABC", client=SecFake(facts_resp=bad))
    assert ei.value.status == 502 and "no se pudieron leer" in ei.value.detail


def test_fetch_facts_without_us_gaap_404():
    with pytest.raises(SEC.SecDataError) as ei:
        SEC.fetch_fundamentals("ABC", client=SecFake(facts_resp=_Resp(200, {"facts": {}})))
    assert ei.value.status == 404


# ---------- endpoint /api/fundamentals/{ticker}/sec ----------

SEC_RESULT = {"data": {"revenue": 110_000, "eps": 5.0}, "period_end": "2025-12-31",
              "filed": "2026-02-01", "accn": ACC,
              "missing": ["Deuda total (USD)"], "detalle": {"revenue": "Revenues"}}


def _fake_sec(calls):
    def fake(tk, client=None):
        calls.append(tk)
        return dict(SEC_RESULT)
    return fake


def test_sec_endpoint_save_409_replace(isolated, monkeypatch):
    c = isolated
    calls = []
    monkeypatch.setattr(SEC, "fetch_fundamentals", _fake_sec(calls))
    r = c.post("/api/fundamentals/ABC/sec", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["asof"] == "2025-12-31" and body["fundamentals"]["revenue"] == 110_000
    assert body["missing"] == ["Deuda total (USD)"]
    f = c.get("/api/fundamentals/ABC").json()
    assert f["period"] == "anual" and f["unit"] == "USD" and f["shares_unit"] == "acciones"
    assert f["asof"] == "2025-12-31"
    assert "SEC EDGAR" in f["source"] and ACC in f["source"] and "presentado" in f["source"]
    # Ya hay fundamentales: sin confirmación → 409, sin llamar a la SEC
    r = c.post("/api/fundamentals/ABC/sec", json={})
    assert r.status_code == 409 and "Confirma" in r.json()["detail"]
    assert calls == ["ABC"]
    # Con replace_existing → 200 y reemplaza
    calls.clear()
    monkeypatch.setattr(SEC, "fetch_fundamentals",
                        lambda tk, client=None: dict(SEC_RESULT, data={"revenue": 1}))
    r = c.post("/api/fundamentals/ABC/sec", json={"replace_existing": True})
    assert r.status_code == 200 and r.json()["fundamentals"]["revenue"] == 1


def test_sec_endpoint_errors(isolated, monkeypatch):
    c = isolated
    monkeypatch.setattr(SEC, "fetch_fundamentals",
                        lambda *a, **k: (_ for _ in ()).throw(
                            SEC.SecDataError(404, "No hay datos de empresa en la SEC")))
    assert c.post("/api/fundamentals/VOO/sec", json={}).status_code == 404
    assert c.post("/api/fundamentals/TICKERDEMASIADOLARGO/sec", json={}).status_code == 400
