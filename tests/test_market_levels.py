"""Pulso de mercado, ATR y niveles operativos por acción (reglas técnicas, no predicción).

Sin red: fetch_quote/fetch_history se simulan; la fixture global bloquea Yahoo.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_assistant as AI
from app import db as D
from app import marketdata as MD
from app import marketpulse as MP
from app import secdata as SEC
from app.main import app
from app.routes import market as market_routes


# ---------- ATR ----------

def _rows(closes, spread=None, highs=None, lows=None):
    out = []
    for i, c in enumerate(closes):
        row = {"date": f"2026-01-{i + 1:02d}", "close": c, "volume": 1}
        if spread is not None:
            row["high"], row["low"] = c + spread / 2, c - spread / 2
        if highs is not None:
            row["high"], row["low"] = highs[i], lows[i]
        out.append(row)
    return out


def test_atr14_flat_closes_constant_range():
    assert MD.atr14(_rows([100.0] * 20, spread=2)) == 2.0


def test_atr14_gap_uses_max_component():
    closes = [100.0] * 20
    highs = [100.5] * 20
    lows = [99.5] * 20
    highs[-1], lows[-1] = 105.0, 104.0    # gap alcista: |high − close_prev| = 5 > high − low = 1
    atr = MD.atr14(_rows(closes, highs=highs, lows=lows))
    assert atr == round((13 * 1.0 + 5.0) / 14, 4)


def test_atr14_without_high_low_uses_close_diff():
    closes = [100 + (i % 2) * 3 for i in range(20)]   # alterna 100/103 → |Δ| = 3
    assert MD.atr14(_rows(closes)) == 3.0


def test_atr14_needs_15_rows():
    assert MD.atr14(_rows([100.0] * 14, spread=2)) is None
    assert MD.atr14(_rows([100.0] * 15, spread=2)) == 2.0


# ---------- niveles ----------

def test_niveles_from_price_and_atr():
    n = MD._niveles(100.0, 2.0, 50.0, 99.0, 98.0, 95.0, 97.0, 0.5)
    assert n["stop_loss"] == 96.0 and n["stop_loss_pct"] == -4.0
    assert n["toma_parcial"] == 106.0 and n["toma_parcial_pct"] == 6.0
    assert n["entrada_zona"] == [98.0, 100.0]          # max(soporte 97, 100 − 2)
    assert n["entrada_nota"].startswith("Compra escalonada")
    assert n["semaforo"] == "neutral" and n["tipo_dia"] == "normal"
    assert "no predicción" in n["regla"]
    # soporte por encima de p − ATR manda
    assert MD._niveles(100.0, 2.0, 50.0, 99.0, 98.0, 95.0, 99.0, None)["entrada_zona"] == [99.0, 100.0]


def test_niveles_semaforo_and_day_type():
    estirada = MD._niveles(100.0, 2.0, 72.0, 97.5, 98.0, 95.0, 97.0, 2.5)
    assert estirada["entrada_zona"] is None and estirada["semaforo"] == "estirada"
    assert "media de 20 días ($97.5)" in estirada["entrada_nota"] and estirada["tipo_dia"] == "verde"
    assert MD._niveles(100.0, 2.0, 30.0, 99.0, 98.0, 95.0, 97.0, -2.0)["semaforo"] == "descuento"
    assert MD._niveles(100.0, 2.0, 30.0, 99.0, 98.0, 95.0, 97.0, -2.0)["tipo_dia"] == "rojo"
    # p < sma200 y sma50 < sma200 → bajista (aunque el RSI sea bajo, no hay descuento bajo la SMA200)
    assert MD._niveles(100.0, 2.0, 30.0, 101.0, 105.0, 110.0, 97.0, None)["semaforo"] == "bajista"
    assert MD._niveles(100.0, 2.0, 50.0, 101.0, 105.0, 110.0, 97.0, None)["semaforo"] == "bajista"
    assert MD._niveles(100.0, 2.0, 50.0, 101.0, 105.0, 110.0, 97.0, None)["tipo_dia"] is None
    assert MD._niveles(100.0, None, 50.0, 99.0, 98.0, 95.0, 97.0, None) is None


def test_technical_summary_uses_live_price_and_exposes_levels():
    closes = [100.0 + (i % 2) * 0.02 for i in range(70)]   # casi plana: TR = rango high−low
    rows = _rows(closes, spread=2)
    tec = MD.technical_summary(rows, price=110.0, day_change_pct=-2.5)
    assert tec["precio"] == 110.0 and tec["ultimo_cierre"] == closes[-1]
    assert tec["sma20"] and tec["atr14"] == 2.0
    assert tec["distancia_a_maximo_pct"] == 0.0        # el precio vivo es el máximo
    n = tec["niveles"]
    assert n["precio_base"] == 110.0 and n["stop_loss"] == 106.0 and n["toma_parcial"] == 116.0
    assert n["tipo_dia"] == "rojo"
    # sin precio vivo se usa el último cierre; los campos previos siguen presentes
    old = MD.technical_summary(rows)
    assert old["precio"] == closes[-1]
    for k in ("sma50", "sma200", "rsi14", "tendencia", "soporte_aproximado", "volatilidad_anualizada_pct"):
        assert k in old
    assert MD.technical_summary(rows[:20])["error"]
    short = MD.technical_summary(_rows(closes[:30]))          # sin high/low: ATR por |Δclose|
    assert short["niveles"] is not None


def test_fetch_history_includes_high_low(monkeypatch):
    payload = {"chart": {"result": [{"timestamp": [1_700_000_000, 1_700_086_400, 1_700_172_800],
                                     "indicators": {"quote": [{"close": [10.0, None, 12.0],
                                                               "high": [11.0, 11.5, 13.0],
                                                               "low": [9.0, 9.5, 11.0],
                                                               "volume": [1, 2, 3]}]}}]}}
    monkeypatch.setattr(MD, "_fetch_json", lambda url: payload)
    rows = MD.fetch_history("AAA")["rows"]
    assert len(rows) == 2                                  # el close None se descarta
    assert rows[0] == {"date": rows[0]["date"], "close": 10.0, "volume": 1, "high": 11.0,
                       "low": 9.0, "adjclose": None}   # sin serie adjclose → None
    assert rows[1]["high"] == 13.0 and rows[1]["low"] == 11.0
    del payload["chart"]["result"][0]["indicators"]["quote"][0]["high"]
    assert MD.fetch_history("AAA")["rows"][0]["high"] is None


# ---------- pulso ----------

def _fakes(quotes, hist_closes=None, spy_price=None, fail=()):
    """quotes: ticker → (price, day_change_pct). hist_closes: ticker → lista de cierres."""
    calls = {"quote": [], "history": []}

    def fq(t):
        calls["quote"].append(t)
        if t in fail or t not in quotes:
            raise MD.MarketDataError(f"sin datos para {t}")
        price, chg = quotes[t]
        return {"ticker": t, "price": price, "currency": "USD",
                "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "prueba", "day_change_pct": chg}

    def fh(t, rng="1y"):
        calls["history"].append(t)
        closes = (hist_closes or {}).get(t) or [100.0 + (i % 7) * 0.3 for i in range(220)]
        return {"ticker": t, "source": "prueba", "fetched_at": "2026-03-02T21:00:00+00:00",
                "rows": _rows(closes, spread=1)}
    return fq, fh, calls


BASE = {"SPY": (500.0, 0.2), "QQQ": (430.0, 0.4), "IWM": (200.0, 0.1), "^VIX": (15.0, -1.0),
        "USO": (70.0, 0.0), "TLT": (90.0, 0.3), "GLD": (250.0, 0.5)}


def test_pulse_semaforo_by_vix():
    fq, fh, _ = _fakes({**BASE, "^VIX": (27.0, 5.0)})
    assert MP.pulse(fq, fh)["semaforo"] == "miedo"
    fq, fh, _ = _fakes({**BASE, "^VIX": (21.0, 5.0)})
    assert MP.pulse(fq, fh)["semaforo"] == "cauteloso"
    fq, fh, _ = _fakes(BASE)
    p = MP.pulse(fq, fh)
    assert p["semaforo"] == "normal" and p["tipo_dia"] == "tranquilo"
    assert "VIX en 15.0: calma" in p["lectura"] and "S&P 500 +0.2%" in p["lectura"] and "Nasdaq 100 +0.4%" in p["lectura"]
    assert "Día tranquilo" in p["lectura"]
    assert len(p["instrumentos"]) == 7 and p["fuente"].startswith("Yahoo") and "no es predicción" in p["nota"]


def test_pulse_miedo_by_spy_below_sma200():
    closes = [600.0] * 220                              # SMA200 = 600 > precio vivo 500
    fq, fh, _ = _fakes({**BASE, "^VIX": (15.0, 0.0)}, hist_closes={"SPY": closes})
    p = MP.pulse(fq, fh)
    assert p["semaforo"] == "miedo"
    spy = next(i for i in p["instrumentos"] if i["ticker"] == "SPY")
    assert spy["sma200"] == 600.0 and spy["price"] == 500.0


def test_pulse_day_type_and_lectura():
    fq, fh, _ = _fakes({**BASE, "SPY": (500.0, -1.8), "^VIX": (27.0, 10.0)})
    p = MP.pulse(fq, fh)
    assert p["tipo_dia"] == "rojo" and "Día rojo con miedo alto" in p["lectura"] and "-1.8%" in p["lectura"]
    fq, fh, _ = _fakes({**BASE, "SPY": (500.0, -1.2)})
    p = MP.pulse(fq, fh)
    assert p["tipo_dia"] == "rojo" and "compras escalonadas" in p["lectura"]
    fq, fh, _ = _fakes({**BASE, "SPY": (500.0, 1.5)})
    p = MP.pulse(fq, fh)
    assert p["tipo_dia"] == "verde" and "Día verde fuerte" in p["lectura"]


def test_pulse_instrument_error_does_not_abort():
    fq, fh, _ = _fakes(BASE, fail=("GLD",))
    p = MP.pulse(fq, fh)
    gld = next(i for i in p["instrumentos"] if i["ticker"] == "GLD")
    assert "error" in gld and p["semaforo"] == "normal"
    fq, fh, _ = _fakes(BASE, fail=("SPY",))
    p = MP.pulse(fq, fh)
    assert p["semaforo"] == "sin_datos" and p["tipo_dia"] is None and "Sin datos" in p["lectura"]


def test_cached_pulse_within_15_min():
    fq, fh, calls = _fakes(BASE)
    t0 = datetime(2026, 3, 2, 21, 0, tzinfo=timezone.utc)
    first = MP.cached_pulse(now=t0, fetch_quote=fq, fetch_history=fh)
    n_q, n_h = len(calls["quote"]), len(calls["history"])
    assert n_q == 7 and n_h == 7
    again = MP.cached_pulse(now=t0 + timedelta(minutes=14), fetch_quote=fq, fetch_history=fh)
    assert again is first and len(calls["quote"]) == n_q and len(calls["history"]) == n_h
    MP.cached_pulse(now=t0 + timedelta(minutes=16), fetch_quote=fq, fetch_history=fh)
    assert len(calls["quote"]) == 14


# ---------- endpoints ----------

@pytest.fixture
def tc(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "levels.db"))
    D.init_db()
    market = {**BASE, "AAA": (110.0, -2.5)}
    fq, fh, calls = _fakes(market, hist_closes={"AAA": [100.0 + (i % 2) * 0.02 for i in range(70)]})
    monkeypatch.setattr(MD, "fetch_quote", fq)
    monkeypatch.setattr(MD, "fetch_history", fh)
    monkeypatch.setattr(SEC, "fetch_fundamentals",
                        lambda tk, client=None: (_ for _ in ()).throw(SEC.SecDataError(404, "sin SEC en pruebas")))
    c = TestClient(app)
    c.calls, c.market = calls, market
    return c


def test_market_pulse_endpoint(tc):
    r = tc.get("/api/market/pulse")
    assert r.status_code == 200
    d = r.json()
    assert d["semaforo"] == "normal" and d["tipo_dia"] == "tranquilo" and len(d["instrumentos"]) == 7
    assert d["fuente"] == "Yahoo Finance (chart API)"


def test_levels_endpoint_with_position_and_cache(tc):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "avg_cost": 100.0, "invested": 200})
    r = c.get("/api/levels/AAA")
    assert r.status_code == 200
    d = r.json()
    assert d["precio"]["valor"] == 110.0 and d["precio"]["day_change_pct"] == -2.5
    n = d["niveles"]
    assert n["stop_loss"] == 108.0 and n["toma_parcial"] == 113.0 and n["tipo_dia"] == "rojo"   # ATR 1
    pos = d["posicion"]
    assert pos["avg_cost"] == 100.0 and pos["qty"] == 2
    assert pos["desde_costo_pct"] == 10.0
    assert pos["stop_desde_costo_pct"] == 8.0 and pos["toma_desde_costo_pct"] == 13.0
    assert d["tecnica"]["fuente"] == "prueba" and "regla" in n
    # la cotización viva queda guardada con su fuente
    assert c.get("/api/portfolio").json()["positions"][0]["price_info"]["fuente"] == "prueba"
    # caché de 10 minutos: la segunda llamada no vuelve a descargar
    n_h = c.calls["history"].count("AAA")
    assert c.get("/api/levels/AAA").status_code == 200
    assert c.calls["history"].count("AAA") == n_h
    market_routes._clear_cache()
    c.get("/api/levels/AAA")
    assert c.calls["history"].count("AAA") == n_h + 1
    # sin posición → posicion None
    assert c.get("/api/levels/SPY").json()["posicion"] is None


def test_levels_endpoint_errors(tc):
    assert tc.get("/api/levels/bad!ticker").status_code == 400
    r = tc.get("/api/levels/ZZZ")
    assert r.status_code == 400 and "No se pudo obtener el precio" in r.json()["detail"]


def test_trade_check_includes_levels_and_market(tc, monkeypatch):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "avg_cost": 100.0, "invested": 200})
    c.put("/api/cash", json={"amount": 500})
    r = c.post("/api/trade_check", json={"ticker": "AAA", "side": "comprar", "amount_usd": 100})
    assert r.status_code == 200
    d = r.json()
    assert d["niveles"]["stop_loss"] == 108.0 and d["niveles"]["semaforo"]
    assert d["mercado_hoy"] == {"semaforo": "normal", "tipo_dia": "tranquilo",
                                "lectura": d["mercado_hoy"]["lectura"]}
    assert d["analisis"]["situacion_tecnica"]["niveles"]["tipo_dia"] == "rojo"   # day_change_pct del precio vivo

    def boom(*a, **k):
        raise RuntimeError("Yahoo caído")
    monkeypatch.setattr(MP, "cached_pulse", boom)
    r = c.post("/api/trade_check", json={"ticker": "AAA", "side": "comprar", "amount_usd": 100})
    assert r.status_code == 200 and r.json()["mercado_hoy"] is None


def test_assistant_context_market_and_levels(tc, monkeypatch):
    c = tc
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "avg_cost": 100.0, "invested": 200})
    conn = D.get_db()
    try:
        uid = D.local_user_id(conn)
        ctx = AI.context_for_user(conn, uid, [{"ticker": "AAA", "qty": 2, "currency": "USD", "invested": 200,
                                               "hapi_value": None, "market_value": None, "unrealized_pl": None,
                                               "return_pct": None, "source": "prueba", "updated_at": None,
                                               "verified": 0, "price_status": "sin_precio"}], {})
        assert ctx["mercado_hoy"]["semaforo"] == "normal"
        assert {i["ticker"] for i in ctx["mercado_hoy"]["instrumentos"]} == {t for t, _ in MP.INSTRUMENTS}
        assert ctx["posiciones"][0]["niveles"]["stop_loss"] == 108.0
        assert "no predicciones" in AI.INSTRUCTIONS

        def boom(*a, **k):
            raise RuntimeError("Yahoo caído")
        monkeypatch.setattr(MP, "cached_pulse", boom)
        monkeypatch.setattr(MP, "cached_levels", boom)
        monkeypatch.setattr(MP, "levels_if_cached", boom)
        ctx = AI.context_for_user(conn, uid, [], {})
        assert ctx["mercado_hoy"] is None and ctx["posiciones"] == []
    finally:
        conn.close()
