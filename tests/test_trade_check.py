"""POST /api/trade_check y /api/trade_check/{id}/luna.

BD aislada con tmp_path; fetch_quote, fetch_history y secdata siempre mockeados:
la prueba nunca toca la red ni el proveedor de IA.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_review as RV
from app import db as D
from app import decisions as DE
from app import marketdata as MD
from app import secdata as SEC
from app.main import app

SEC_RESULT = {"data": {"revenue": 110_000, "eps": 5.0}, "period_end": "2025-12-31",
              "filed": "2026-02-01", "accn": "0000-00-000010",
              "missing": [], "detalle": {"revenue": "Revenues"}}


@pytest.fixture
def tc(tmp_path, monkeypatch):
    """Cliente con BD aislada y mercado/SEC simulados. `c.quotes` marca qué
    tickers cotizan; `c.sec_calls` registra las llamadas automáticas a la SEC."""
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "isolated.db"))
    D.init_db()
    quotes = {}
    sec_calls = []

    def fake_quote(t):
        tk = t.upper()
        if tk not in quotes:
            raise MD.MarketDataError(f"sin datos de prueba para {tk}")
        return {"ticker": tk, "price": quotes[tk], "currency": "USD",
                "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "prueba", "day_change_pct": None}

    def fake_history(t, rng="1y"):
        raise MD.MarketDataError("sin histórico de prueba")

    def fake_sec(tk, client=None):
        sec_calls.append(tk)
        if tk == "VOO":
            raise SEC.SecDataError(404, "No hay datos de empresa en la SEC para VOO: "
                                        "los ETF y fondos no presentan 10-K.")
        return dict(SEC_RESULT)

    monkeypatch.setattr(MD, "fetch_quote", fake_quote)
    monkeypatch.setattr(MD, "fetch_history", fake_history)
    monkeypatch.setattr(SEC, "fetch_fundamentals", fake_sec)
    c = TestClient(app)
    c.quotes, c.sec_calls = quotes, sec_calls
    return c


def _decisions(c):
    return c.get("/api/decisions").json()["decisions"]


def test_motor_qty0_mantener_esperar():
    """Sin posición, una propuesta de mantener se convierte en esperar."""
    d = DE.evaluate_position({"ticker": "XYZ", "price": 100, "price_status": "actual",
                              "qty": 0, "market_value": 0, "weight_pct": 0,
                              "margin_of_safety_pct": 0.0, "fundamentals": True,
                              "has_thesis": True, "technical": None,
                              "profile_complete": True})
    assert d["decision_propuesta"] == "esperar"
    assert any("No tienes esta acción" in a for a in d["argumentos"])


def test_buy_not_held_sufficient_cash(tc):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "invested": 180})
    c.put("/api/cash", json={"amount": 500})
    c.quotes.update({"AAA": 110.0, "BBB": 50.0})
    r = c.post("/api/trade_check", json={"ticker": "BBB", "side": "comprar", "amount_usd": 100})
    assert r.status_code == 200
    d = r.json()
    assert d["acciones_aprox"] == round(100 / 50, 6)
    assert d["peso_antes_pct"] == 0
    assert abs(d["peso_despues_pct"] - round(100 / 720 * 100, 2)) < 1e-9  # total 220+500
    assert d["efectivo_antes"] == 500 and d["efectivo_despues"] == 400
    assert d["deposito_necesario"] == 0 and d["efectivo_suficiente"] is True
    assert len(d["limites"]) == 4
    # la evaluación queda guardada en la decisión para Luna y el registro
    row = next(x for x in _decisions(c) if x["id"] == d["decision_id"])
    assert row["proposal"]["operacion_evaluada"]["ticker"] == "BBB"
    assert c.sec_calls == ["BBB"]          # sin fundamentales → intento automático
    f = c.get("/api/fundamentals/BBB").json()
    assert f["source"].startswith("SEC EDGAR") and f["period"] == "anual"


def test_buy_insufficient_cash(tc):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "invested": 180})
    c.put("/api/cash", json={"amount": 40})
    c.quotes.update({"AAA": 110.0, "BBB": 50.0})
    r = c.post("/api/trade_check", json={"ticker": "BBB", "side": "comprar", "amount_usd": 100})
    assert r.status_code == 200
    d = r.json()
    assert d["deposito_necesario"] == 60.0                    # monto − efectivo
    assert d["efectivo_despues"] == 0                         # tras depositar lo justo
    assert d["efectivo_suficiente"] is False
    assert abs(d["total_despues"] - (d["total_antes"] + 60.0)) < 1e-9


def test_sell_ok(tc):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "invested": 180})
    c.put("/api/cash", json={"amount": 50})
    c.quotes["AAA"] = 110.0   # posición vale $220
    r = c.post("/api/trade_check", json={"ticker": "AAA", "side": "vender", "amount_usd": 100})
    assert r.status_code == 200
    d = r.json()
    assert d["efectivo_despues"] == 150.0
    assert d["peso_antes_pct"] > d["peso_despues_pct"]
    assert d["deposito_necesario"] == 0


def test_sell_over_and_not_held_are_400_before_sec_and_analysis(tc):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "invested": 180})
    c.quotes.update({"AAA": 110.0, "CCC": 10.0})
    n0 = len(_decisions(c))
    r = c.post("/api/trade_check", json={"ticker": "AAA", "side": "vender", "amount_usd": 1000})
    assert r.status_code == 400 and "Solo tienes" in r.json()["detail"]
    r = c.post("/api/trade_check", json={"ticker": "CCC", "side": "vender", "amount_usd": 50})
    assert r.status_code == 400 and "No tienes CCC" in r.json()["detail"]
    assert c.sec_calls == []               # ninguna consulta a la SEC
    assert len(_decisions(c)) == n0        # ninguna decisión creada


def test_quote_failure_400(tc):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 1, "invested": 50})
    c.quotes["AAA"] = 100.0                # ZZZ no cotiza
    r = c.post("/api/trade_check", json={"ticker": "ZZZ", "side": "comprar", "amount_usd": 50})
    assert r.status_code == 400
    assert "No se pudo obtener el precio de ZZZ" in r.json()["detail"]


def test_sec_not_called_when_fundamentals_exist(tc):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 1, "invested": 50})
    c.put("/api/fundamentals/BBB", json={"data": {"revenue": 5}, "source": "informe propio",
                                         "asof": "2026-01-01"})
    c.quotes.update({"AAA": 100.0, "BBB": 50.0})
    r = c.post("/api/trade_check", json={"ticker": "BBB", "side": "comprar", "amount_usd": 100})
    assert r.status_code == 200
    assert c.sec_calls == []               # fundamentales existentes: nunca reemplaza
    f = c.get("/api/fundamentals/BBB").json()
    assert f["source"] == "informe propio"


def test_sec_error_becomes_fundamentales_nota(tc):
    c = tc
    c.quotes["VOO"] = 500.0
    r = c.post("/api/trade_check", json={"ticker": "VOO", "side": "comprar", "amount_usd": 50})
    assert r.status_code == 200
    assert "ETF" in r.json()["fundamentales_nota"]


def test_luna_endpoint(tc, monkeypatch):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "invested": 180})
    c.quotes.update({"AAA": 110.0, "BBB": 50.0})
    # decisión sin operacion_evaluada → 400
    c.post("/api/prices/manual", json={"ticker": "AAA", "price": 110.0,
                                       "asof": datetime.now(timezone.utc).date().isoformat(),
                                       "source": "prueba"})
    did = c.post("/api/analysis/AAA", json={}).json()["decision_id"]
    r = c.post(f"/api/trade_check/{did}/luna")
    assert r.status_code == 400 and "Evalúa la operación" in r.json()["detail"]
    # con operación evaluada: respuesta mockeada → 200; ReviewError → 502
    did = c.post("/api/trade_check",
                 json={"ticker": "BBB", "side": "comprar", "amount_usd": 100}).json()["decision_id"]
    monkeypatch.setattr(RV, "trade_opinion",
                        lambda op: {"resumen": "ok", "a_favor": ["a"], "en_contra": ["b"],
                                    "vigilar": ["¿Sigue la tesis?"], "model": "luna-prueba"})
    r = c.post(f"/api/trade_check/{did}/luna")
    assert r.status_code == 200 and r.json()["resumen"] == "ok"

    def boom(op):
        raise RV.ReviewError("fallo de prueba")
    monkeypatch.setattr(RV, "trade_opinion", boom)
    assert c.post(f"/api/trade_check/{did}/luna").status_code == 502
