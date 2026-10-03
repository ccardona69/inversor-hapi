"""GET /api/metricas: exposición ETF, costo por depósito, compras al plan y
costo de la herramienta — cada una con su etiqueta y SIN DATO cuando falta."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import db as D
from app.main import app


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "metricas.db"))
    D.init_db()
    return TestClient(app)


def _trade(ticker, qty, price, at, side="comprar"):
    conn = D.get_db()
    conn.execute("INSERT INTO trades (user_id, ticker, side, qty, price, at, created_at) "
                 "VALUES (?,?,?,?,?,?,?)",
                 (D.local_user_id(conn), ticker, side, qty, price, at, D.now()))
    conn.commit()
    conn.close()


def _price(ticker, price):
    conn = D.get_db()
    conn.execute("INSERT INTO prices (ticker, price, currency, asof, source, created_at) "
                 "VALUES (?,?,?,?,?,?)",
                 (ticker, price, "USD",
                  datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "prueba", D.now()))
    conn.commit()
    conn.close()


def test_sin_datos(isolated):
    r = isolated.get("/api/metricas")
    assert r.status_code == 200
    d = r.json()
    assert d["etf_pct"]["etiqueta"] == "SIN DATO" and d["etf_pct"]["valor"] is None
    assert d["compras_al_plan"]["valor_pct"] is None
    assert d["compras_al_plan"]["etiqueta"] == "SIN DATO"
    assert d["compras_al_plan"]["n_compras"] == 0
    assert d["costo_sistema"]["etiqueta"] == "SIN DATO"
    assert d["costo_sistema"]["mensual_usd"] is None
    assert d["revision_abandono"] == "2027-01-02"


def test_compras_al_plan_desde_plan_inicio(isolated):
    _trade("SPY", 1, 100, "2026-10-05")     # 100 USD al ETF del plan
    _trade("AMZN", 1, 50, "2026-10-06")     # 50 USD fuera del plan
    _trade("SPY", 1, 999, "2026-09-01")     # anterior a plan_inicio: no cuenta
    _trade("SPY", 1, 777, "2026-10-07", side="vender")  # ventas no cuentan
    d = isolated.get("/api/metricas").json()["compras_al_plan"]
    assert d["n_compras"] == 2
    assert d["usd_total"] == 150 and d["usd_etf"] == 100
    assert d["valor_pct"] == 66.67
    assert d["etiqueta"] == "CÁLCULO" and d["desde"] == "2026-10-02"


def test_costo_sistema(isolated):
    c = isolated
    # cartera con valor para el porcentaje anual
    c.post("/api/positions", json={"ticker": "AAA", "qty": 10, "invested": 1200})
    c.post("/api/positions/AAA/verify", json={"evidencia": "captura de prueba"})
    _price("AAA", 120.0)                                     # base = 1200
    assert c.put("/api/metricas/costo_sistema", json={"mensual_usd": 10}).status_code == 200
    d = c.get("/api/metricas").json()["costo_sistema"]
    assert d["mensual_usd"] == 10 and d["anual_usd"] == 120
    assert d["pct_cartera"] == 10.0                          # 120/1200
    assert d["etiqueta"] == "CÁLCULO (HR)"


def test_costo_sistema_validacion(isolated):
    assert isolated.put("/api/metricas/costo_sistema",
                        json={"mensual_usd": -5}).status_code == 400
    assert isolated.put("/api/metricas/costo_sistema",
                        json={"mensual_usd": "10"}).status_code == 400
    assert isolated.put("/api/metricas/costo_sistema",
                        json={"mensual_usd": 10001}).status_code == 400
    assert isolated.put("/api/metricas/costo_sistema", json={}).status_code == 400
