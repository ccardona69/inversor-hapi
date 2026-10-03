"""Modo plan (Ulises): la puerta común de las «sirenas» y la respuesta
determinista de trade_check cuando el ETF está bajo su meta.

Sin la fixture sin_modo_plan: aquí el modo se deja activar de verdad
(cartera vacía ⇒ sin dato de exposición ⇒ activo por fail-closed).
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import brecha as BR
from app import db as D
from app import marketdata as MD
from app.main import app


# ---------- la función pura ----------


def test_modo_plan_tabla_de_verdad():
    assert BR.modo_plan(None, 50) == {"activo": True, "etf_pct": None, "meta_pct": 50,
                                    "motivo": "sin dato de exposición: cuenta como bajo la meta"}
    assert BR.modo_plan(40.0, 50) == {"activo": True, "etf_pct": 40.0, "meta_pct": 50,
                                     "motivo": "ETF bajo la meta del plan"}
    assert BR.modo_plan(50, 50) == {"activo": False, "etf_pct": 50, "meta_pct": 50,
                                   "motivo": None}
    assert BR.modo_plan(60, 50)["activo"] is False
    assert BR.modo_plan(60, None)["activo"] is True      # sin meta: fail-closed
    assert BR.modo_plan(None, None)["activo"] is True


# ---------- la puerta sobre la API ----------


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "modo_plan.db"))
    D.init_db()
    return TestClient(app)


def _price(ticker, price):
    conn = D.get_db()
    conn.execute("INSERT INTO prices (ticker, price, currency, asof, source, created_at) "
                 "VALUES (?,?,?,?,?,?)",
                 (ticker, price, "USD",
                  datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "prueba", D.now()))
    conn.commit()
    conn.close()


CERRADAS = [
    ("GET", "/api/radar", None),
    ("POST", "/api/radar/refresh", None),
    ("POST", "/api/radar/AAA", None),
    ("GET", "/api/market/pulse", None),
    ("GET", "/api/levels/AAA", None),
    ("POST", "/api/trade_check/1/luna", None),
    ("POST", "/api/decisions/1/explain", None),
    ("POST", "/api/journal/1/challenge", None),
    ("POST", "/api/assistant/ask", {"question": "¿compro AAA?"}),
    ("POST", "/api/fundamentals/photo/analyze", {"image_b64": "YQ==", "mime": "image/png"}),
    ("POST", "/api/fundamentals/AAA/sec", {}),
]


@pytest.mark.parametrize("method,path,body", CERRADAS)
def test_funciones_cerradas_devuelven_409(isolated, method, path, body):
    """Cartera vacía ⇒ sin dato de exposición ⇒ modo plan activo (fail-closed)."""
    r = isolated.request(method, path, json=body)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["modo_plan"] is True
    assert "Modo plan activo" in detail["message"]
    assert detail["motivo"] == "sin dato de exposición: cuenta como bajo la meta"


def test_analysis_etf_no_pasa_por_la_puerta(isolated):
    """/api/analysis/SPY puede fallar por falta de precio (400) pero jamás
    por la puerta del modo plan: el ETF del plan sí se analiza."""
    r = isolated.post("/api/analysis/SPY", json={})
    assert r.status_code != 409


def test_analysis_accion_cerrada(isolated):
    r = isolated.post("/api/analysis/AMZN", json={})
    assert r.status_code == 409 and r.json()["detail"]["modo_plan"] is True


# ---------- trade_check en modo plan ----------


def test_trade_check_compra_accion_bloqueada_sin_red(isolated, monkeypatch):
    """La respuesta es determinista: ni precio, ni SEC, ni decisión registrada."""
    def boom(t):
        raise AssertionError("trade_check no debió descargar el precio")
    monkeypatch.setattr(MD, "fetch_quote", boom)
    r = isolated.post("/api/trade_check",
                      json={"ticker": "AMZN", "side": "comprar", "amount_usd": 100})
    assert r.status_code == 200
    d = r.json()
    assert d["bloqueado_por_plan"] is True and d["modo_plan"]["activo"] is True
    assert d["decision_id"] is None and d["etf_plan"] == "SPY"
    assert d["cumple_limites"] is False
    assert d["limites"] == [{"limite": "Meta ETF del plan",
                            "valor": d["plan"]["etf_pct_antes"],
                            "maximo": 50, "cumple": False}]
    assert "próximo dinero va al ETF" in d["nota"]
    assert isolated.get("/api/decisions").json()["decisions"] == []


def test_trade_check_compra_etf_flujo_reducido(isolated, monkeypatch):
    """Comprar el ETF del plan sí se evalúa, pero sin fundamentales ni técnica:
    es justamente lo que el plan manda."""
    monkeypatch.setattr(MD, "fetch_quote",
                        lambda t: {"ticker": t.upper(), "price": 500.0, "currency": "USD",
                                   "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                   "source": "prueba", "day_change_pct": None})
    monkeypatch.setattr(MD, "fetch_history",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("completo=False no descarga histórico")))
    r = isolated.post("/api/trade_check",
                      json={"ticker": "SPY", "side": "comprar", "amount_usd": 100})
    assert r.status_code == 200
    d = r.json()
    assert d["bloqueado_por_plan"] is False
    assert d["modo_plan"]["activo"] is True
    for k in ("valoracion", "niveles", "tecnica", "mercado_hoy"):
        assert d[k] is None


def test_etf_verificado_en_meta_desactiva_el_modo(isolated):
    c = isolated
    c.post("/api/positions", json={"ticker": "SPY", "qty": 10, "invested": 5000})
    c.post("/api/positions/SPY/verify", json={"evidencia": "captura de prueba"})
    _price("SPY", 500.0)                       # 5000/5000 = 100 % ≥ meta 50 %
    assert c.get("/api/marcador").json()["modo_plan"]["activo"] is False
    assert c.get("/api/radar").status_code == 200


def test_marcador_y_brecha_incluyen_modo_plan(isolated):
    mc = isolated.get("/api/marcador").json()
    br = isolated.get("/api/brecha").json()
    assert mc["modo_plan"]["activo"] is True
    assert br["modo_plan"]["activo"] is True
