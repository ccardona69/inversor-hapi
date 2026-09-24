"""Regresiones de integridad de posiciones; nunca usa inversor.db."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import db as D
from app import decisions as DE
from app import marketdata as MD
from app import photosync as PS
from app.main import app


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "integrity.db"))
    D.init_db()
    client = TestClient(app)
    assert client.post("/api/register", json={"email": "integridad@test.pe",
                                               "password": "clave-segura-1"}).status_code == 200
    return client


def test_local_home_serves_navigation_without_exposing_private_api(session):
    anon = TestClient(app)
    homepage = anon.get("/")
    assert homepage.status_code == 200
    assert homepage.headers["cache-control"] == "no-cache"
    assert 'href="#analisis"' in homepage.text and 'href="#asistente"' in homepage.text
    assert '<link rel="stylesheet" href="/app.css">' in homepage.text
    styles = anon.get("/app.css")
    assert styles.status_code == 200 and styles.headers["cache-control"] == "no-cache"
    assert '#layout.hidden{display:none}' in styles.text
    assert anon.get("/api/portfolio").status_code == 401
    assert anon.get("/api/assistant/status").status_code == 401


def test_editing_a_verified_position_requires_verification_again(session):
    initial = {"ticker": "NVDA", "qty": 2, "invested": 100, "source": "captura del usuario"}
    assert session.post("/api/positions", json=initial).status_code == 200
    def position():
        return session.get("/api/portfolio").json()["positions"][0]

    assert position()["verified"] == 0
    assert session.post("/api/positions/NVDA/verify").status_code == 200
    assert position()["verified"] == 1

    changed = {**initial, "qty": 3, "invested": 150}
    assert session.post("/api/positions", json=changed).status_code == 200
    assert position()["qty"] == 3 and position()["verified"] == 0

    assert session.post("/api/positions/NVDA/verify").status_code == 200
    assert session.post("/api/hapi/photo/save", json={"rows": [
        {"ticker": "NVDA", "qty": 4, "invested": 200}]}).status_code == 200
    assert position()["qty"] == 4 and position()["verified"] == 0


def test_future_prices_are_not_current_and_invalid_manual_prices_are_rejected(session):
    now = datetime.now(timezone.utc)
    future = (now + timedelta(days=1)).isoformat()
    status = MD.staleness(future)
    assert status["status"] == "fecha_futura" and not status["usable_as_current"]

    valid = {"ticker": "NVDA", "price": 100, "source": "bróker del usuario",
             "asof": now.isoformat(timespec="seconds")}
    for changes in ({"price": 0}, {"price": -1}, {"asof": "sin fecha"},
                    {"asof": future}, {"source": " "}, {"ticker": " "}):
        result = session.post("/api/prices/manual", json={**valid, **changes})
        assert result.status_code == 400, result.text
    conn = D.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 0
    finally:
        conn.close()
    assert session.post("/api/prices/manual", json=valid).status_code == 200


def test_future_price_already_in_database_is_flagged(session):
    assert session.post("/api/positions", json={"ticker": "TEST", "qty": 1,
                                                  "source": "usuario"}).status_code == 200
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    conn = D.get_db()
    try:
        conn.execute("INSERT INTO prices (ticker, price, asof, source, created_at) "
                     "VALUES (?, ?, ?, ?, ?)", ("TEST", 99, future, "dato erróneo", D.now()))
        conn.commit()
    finally:
        conn.close()
    pf = session.get("/api/portfolio").json()["positions"][0]
    assert pf["price_status"] == "fecha_futura"
    assert pf["market_value"] is None
    alerts = session.get("/api/alerts").json()["alerts"]
    assert any("TEST: precio fecha futura" in a["text"] for a in alerts)


def test_analysis_rejects_stale_price_and_screenshot_without_quote(session, monkeypatch):
    assert session.post("/api/positions", json={"ticker": "TEST", "qty": 1,
        "hapi_value": 120, "source": "captura del usuario"}).status_code == 200
    no_quote = session.post("/api/analysis/TEST", json={})
    assert no_quote.status_code == 400 and "captura" in no_quote.json()["detail"]

    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    assert session.post("/api/prices/manual", json={"ticker": "TEST", "price": 100,
        "asof": old, "source": "precio antiguo"}).status_code == 200
    stale = session.post("/api/analysis/TEST", json={})
    assert stale.status_code == 400 and "desactualizado" in stale.json()["detail"]

    conn = D.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    finally:
        conn.close()

    # Una cotización fechada y vigente sí permite el análisis, aun sin histórico externo.
    assert session.post("/api/prices/manual", json={"ticker": "TEST", "price": 105,
        "asof": datetime.now(timezone.utc).isoformat(), "source": "bróker del usuario"}).status_code == 200
    def offline(_ticker):
        raise MD.MarketDataError("histórico no disponible")
    monkeypatch.setattr(MD, "fetch_history", offline)
    fresh = session.post("/api/analysis/TEST", json={})
    assert fresh.status_code == 200
    assert fresh.json()["precio_actual"]["fuente"] == "bróker del usuario"


def test_incomplete_portfolio_does_not_invent_totals_or_risk(session):
    for ticker, value in (("AAA", None), ("BBB", 120)):
        assert session.post("/api/positions", json={"ticker": ticker, "qty": 1,
            "invested": 100, "hapi_value": value, "source": "captura antigua"}).status_code == 200
    assert session.post("/api/prices/manual", json={"ticker": "AAA", "price": 110,
        "asof": datetime.now(timezone.utc).isoformat(), "source": "precio reciente"}).status_code == 200

    portfolio = session.get("/api/portfolio").json()
    assert portfolio["totals"]["valor_actual"] is None
    assert portfolio["totals"]["resultado"] is None
    assert portfolio["totals"]["pesos_pct"] == {}
    assert portfolio["totals"]["sin_precio_vigente"] == ["BBB"]
    assert next(p for p in portfolio["positions"] if p["ticker"] == "BBB")["market_value"] == 120
    assert "error" in session.get("/api/risk").json()
    assert session.post("/api/simulate", json={"changes": {"AAA": -10}}).status_code == 400
    blocked = session.post("/api/analysis/AAA", json={})
    assert blocked.status_code == 400 and "BBB" in blocked.json()["detail"]
    alerts = session.get("/api/alerts").json()["alerts"]
    assert any(a["type"] == "cartera_incompleta" for a in alerts)
    assert not any(a["type"] == "limite_excedido" for a in alerts)

    assert session.post("/api/prices/manual", json={"ticker": "BBB", "price": 130,
        "asof": datetime.now(timezone.utc).isoformat(), "source": "precio reciente"}).status_code == 200
    after = session.get("/api/portfolio").json()["totals"]
    assert after["valor_actual"] == 240 and after["resultado"] == 40
    assert after["pesos_pct"]["AAA"] > 0
    assert "error" not in session.get("/api/risk").json()


def test_screenshot_value_is_not_current_profit(session):
    assert session.post("/api/positions", json={"ticker": "TEST", "qty": 1,
        "invested": 100, "hapi_value": 130, "source": "captura antigua"}).status_code == 200
    position = session.get("/api/portfolio").json()["positions"][0]
    assert position["market_value"] == 130  # referencia visible, no cotización
    assert position["unrealized_pl"] is None and position["return_pct"] is None
    assert position["price_info"]["asof"]


def test_currency_mismatch_blocks_valuation_risk_and_decisions(session):
    assert session.post("/api/positions", json={"ticker": "TEST", "qty": 1,
        "invested": 100, "source": "usuario"}).status_code == 200
    assert session.post("/api/prices/manual", json={"ticker": "TEST", "price": 120,
        "currency": "EUR", "asof": datetime.now(timezone.utc).isoformat(),
        "source": "precio en euros"}).status_code == 200
    pf = session.get("/api/portfolio").json()
    assert pf["positions"][0]["price_status"] == "moneda_incompatible"
    assert pf["totals"]["valor_actual"] is None
    assert "error" in session.get("/api/risk").json()
    assert session.post("/api/analysis/TEST", json={}).status_code == 400
    assert session.post("/api/simulate", json={}).status_code == 400


def test_foreign_cash_does_not_enter_usd_risk(session):
    assert session.put("/api/cash", json={"amount": 100, "currency": "EUR"}).status_code == 400
    assert session.post("/api/positions", json={"ticker": "TEST", "qty": 1,
        "invested": 100, "source": "usuario"}).status_code == 200
    assert session.post("/api/prices/manual", json={"ticker": "TEST", "price": 110,
        "asof": datetime.now(timezone.utc).isoformat(), "source": "USD"}).status_code == 200
    conn = D.get_db()
    try:
        conn.execute("INSERT INTO cash (user_id, amount, currency, updated_at) VALUES (1, 30, 'EUR', ?)", (D.now(),))
        conn.commit()
    finally:
        conn.close()
    pf = session.get("/api/portfolio").json()
    assert pf["cash"] is None and pf["cash_currency"] == "EUR"
    assert "error" in session.get("/api/risk").json()
    assert session.post("/api/simulate", json={}).status_code == 400
    assert session.post("/api/analysis/TEST", json={}).status_code == 400
    assert any(a["type"] == "moneda_efectivo" for a in session.get("/api/alerts").json()["alerts"])
    assert session.put("/api/cash", json={"amount": 30, "currency": "USD"}).status_code == 200
    assert session.get("/api/portfolio").json()["cash"] == 30


def test_simulation_does_not_invent_return_without_cost():
    result = DE.simulate([{"ticker": "AAA", "market_value": 100, "invested": None}], 0, {}, [])
    assert result["resultado_vs_invertido"] is None


def test_photo_nonfinite_values_are_missing_not_portfolio_numbers():
    rows, omitted = PS.normalize_rows([
        {"ticker": "AAA", "qty": 1, "value": "NaN", "invested": "Infinity"},
        {"ticker": "BBB", "qty": "NaN"},
    ])
    assert len(omitted) == 1
    assert rows[0]["hapi_value"] is None and rows[0]["invested"] is None
