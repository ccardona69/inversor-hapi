"""Radar de oportunidades: universo, screen puro y endpoints.

Las pruebas de endpoint usan una BD aislada con tmp_path y la red siempre está
mockeada (fetch_quote / fetch_history / SEC.fetch_fundamentals).
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import analysis as AN
from app import db as D
from app import marketdata as MD
from app import radar as RADAR
from app import secdata as SEC
from app import tradesync as TS
from app.main import app

# La suite previa prueba el interior de las funciones; la puerta del
# modo plan (409 con el ETF bajo la meta) se abre con el estado inactivo.
pytestmark = pytest.mark.usefixtures("sin_modo_plan")



@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "isolated.db"))
    D.init_db()
    return TestClient(app)


# DATOS DE PRUEBA (no reales): sirven para validar los cálculos
FUND = {"revenue": 100_000, "revenue_growth_pct": 40.0, "eps": 5.0,
        "fcf": 40_000, "shares_out": 20_000, "debt": 30_000, "cash": 80_000,
        "gross_margin_pct": 50, "op_margin_pct": 20, "roic_pct": 15,
        "moat": "marca y escala (prueba)", "key_risks": "competencia (prueba)"}

FUND_BAD = {"revenue": 10_000, "revenue_growth_pct": 10.0, "eps": 0.5,
            "fcf": 5_000, "shares_out": 20_000, "debt": 50_000, "cash": 10_000,
            "gross_margin_pct": 10, "op_margin_pct": 2, "roic_pct": 1}


def _fair(fund, g):
    return AN.dcf_per_share(fund["fcf"], fund["shares_out"],
                            {**AN.DEFAULT_DCF, "growth_1_5_pct": g})


# ---------- universo ----------

def test_universe():
    assert len(RADAR.UNIVERSE) == 78
    assert len(set(RADAR.UNIVERSE)) == 78          # sin duplicados
    for tk, sector in RADAR.UNIVERSE.items():
        assert TS.TICKER.fullmatch(tk)
        assert isinstance(sector, str) and sector  # sector en español, no vacío


# ---------- screen (pura) ----------

def test_screen_verdicts_por_regla():
    fund = dict(FUND)
    fair = _fair(fund, 15)
    assert fair and fair > 0
    assert RADAR.screen("X", "S", fair * 0.7, fund)["veredicto"] == "barata_y_buena"
    assert RADAR.screen("X", "S", fair, fund)["veredicto"] == "precio_justo"
    assert RADAR.screen("X", "S", fair * 1.6, fund)["veredicto"] == "buena_pero_cara"


def test_screen_calidad_es_media_de_scores():
    s = RADAR.screen("X", "S", 100.0, dict(FUND))
    vals = [v["score"] for v in AN.fundamental_scores(FUND)["scores"].values()
            if v["score"] is not None]
    assert s["calidad"] == round(sum(vals) / len(vals), 1)
    assert s["calidad"] >= 6


def test_screen_cuidado_y_peor_score():
    s = RADAR.screen("X", "S", 1.0, dict(FUND_BAD))
    assert s["calidad"] is not None and s["calidad"] < 6
    assert s["veredicto"] == "cuidado"
    # además de los hechos, se agrega el motivo del peor score
    assert len(s["motivos"]) >= 2 and "Margen bruto" in s["motivos"][-1]


def test_screen_faltan_datos():
    # sin fundamentales: no hay calidad ni mos
    s = RADAR.screen("X", "S", 100.0, {})
    assert s["calidad"] is None and s["mos"] is None
    assert s["veredicto"] == "faltan_datos"
    # sin precio: hay calidad pero mos no calculable
    s2 = RADAR.screen("X", "S", None, dict(FUND))
    assert s2["veredicto"] == "faltan_datos" and s2["mos"] is None
    # sin crecimiento: mos None aunque haya precio y fundamentales
    fund = dict(FUND)
    fund.pop("revenue_growth_pct")
    s3 = RADAR.screen("X", "S", 100.0, fund)
    assert s3["veredicto"] == "faltan_datos" and s3["calidad"] is not None


def test_screen_crecimiento_conservador_acotado():
    price = 100.0
    # growth 40 → supuesto de 15 (acotado), no el real
    s = RADAR.screen("X", "S", price, dict(FUND))
    esperado = AN.valuation_scenarios(price, dict(FUND), {"growth_1_5_pct": 15})
    assert s["mos"] == esperado["escenarios"]["base"]["margen_de_seguridad_pct"]
    # growth negativo → supuesto de 0
    fund_neg = dict(FUND, revenue_growth_pct=-5.0)
    s2 = RADAR.screen("X", "S", price, fund_neg)
    esperado2 = AN.valuation_scenarios(price, fund_neg, {"growth_1_5_pct": 0})
    assert s2["mos"] == esperado2["escenarios"]["base"]["margen_de_seguridad_pct"]


def test_screen_pe_pfcf_crec():
    s = RADAR.screen("X", "S", 100.0, dict(FUND))
    assert s["pe"] == 20.0          # 100 / 5.0
    assert s["pfcf"] == 50.0        # 100 / (40000/20000)
    assert s["crec"] == 40.0
    # EPS negativo → sin P/E
    s2 = RADAR.screen("X", "S", 100.0, dict(FUND, eps=-1.0))
    assert s2["pe"] is None


# ---------- GET /api/radar (sin red) ----------

def test_radar_get(isolated):
    c = isolated
    c.post("/api/positions", json={"ticker": "AAA", "qty": 1, "invested": 100,
                                   "sector": "Sector propio"})
    c.post("/api/candidates", json={"ticker": "ZZX", "name": "manual",
                                    "source": "análisis propio", "data": {"tesis": "x"}})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    c.post("/api/prices/manual", json={"ticker": "AAA", "price": 10.0,
                                       "asof": now, "source": "prueba manual"})
    c.put("/api/fundamentals/AAA", json={"data": FUND, "source": "prueba",
                                         "asof": "2026-01-01"})
    r = c.get("/api/radar").json()
    assert r["universo"] == 78 and "no es toda la bolsa" in r["nota"]
    items = {i["ticker"]: i for i in r["items"]}
    assert len(items) == 80                       # 78 + AAA + ZZX
    aaa = items["AAA"]
    assert aaa["en_cartera"] and not aaa["en_watchlist"] and not aaa["en_universo"]
    assert aaa["sector"] == "Sector propio"
    assert aaa["price"]["price"] == 10.0 and aaa["price"]["status"] == "actual"
    assert aaa["fund"]["source"] == "prueba"
    assert aaa["veredicto"] != "faltan_datos"     # precio bajo + FCF → mos calculable
    zzx = items["ZZX"]
    assert zzx["en_watchlist"] and zzx["candidate_id"] and not zzx["en_cartera"]
    aapl = items["AAPL"]
    assert aapl["en_universo"] and aapl["sector"] == "Tecnología"
    assert aapl["veredicto"] == "faltan_datos"    # sin precio ni fundamentales
    assert items["AMZN"]["sector"] == "Consumo/Tecnología"
    assert items["TSLA"]["sector"] == "Automotriz/Tecnología"
    assert items["NEE"]["sector"] == "Servicios públicos"
    # orden: veredictos con datos primero, faltan_datos al final
    verds = [i["veredicto"] for i in r["items"]]
    ultimo_con_datos = max(i for i, v in enumerate(verds) if v != "faltan_datos")
    assert verds.index("faltan_datos") > ultimo_con_datos


# ---------- POST /api/radar/refresh (red mockeada) ----------

def _mocks(monkeypatch, fail_quote=(), fail_sec=()):
    calls, sec_calls = [], []

    def fake_quote(tk):
        calls.append(tk)
        if tk in fail_quote:
            raise MD.MarketDataError("sin datos de prueba")
        return {"ticker": tk, "price": 100.0, "currency": "USD",
                "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "Yahoo (prueba)", "day_change_pct": 1.0}

    def fake_sec(tk, client=None):
        sec_calls.append(tk)
        if tk in fail_sec:
            raise SEC.SecDataError(502, "SEC caída (prueba)")
        return {"data": dict(FUND), "period_end": "2025-12-31",
                "filed": "2026-02-01", "accn": "x", "missing": [], "detalle": {}}

    monkeypatch.setattr(MD, "fetch_quote", fake_quote)
    monkeypatch.setattr(MD, "fetch_history", lambda *a, **k: {"rows": []})
    monkeypatch.setattr(SEC, "fetch_fundamentals", fake_sec)
    return calls, sec_calls


def test_radar_refresh(isolated, monkeypatch):
    c = isolated
    calls, sec_calls = _mocks(monkeypatch, fail_quote={"AAPL"}, fail_sec={"MSFT"})
    c.post("/api/candidates", json={"ticker": "ZZX", "source": "propio", "data": {}})
    r = c.post("/api/radar/refresh").json()
    assert r["ok"] is True
    total = 79                                    # 78 universo + ZZX
    assert r["precios"] == total - 1              # solo AAPL falló
    assert r["fundamentales_nuevos"] == total - 1  # solo MSFT falló
    assert set(calls) == set(sec_calls) and len(calls) == total
    errores = {e["ticker"] for e in r["errores"]}
    assert errores == {"AAPL", "MSFT"}            # por ticker, sin abortar

    # segunda pasada: solo reintenta los fundamentales que faltan (MSFT);
    # los precios se refrescan siempre, así que AAPL vuelve a fallar
    r2 = c.post("/api/radar/refresh").json()
    assert r2["fundamentales_nuevos"] == 0 and len(sec_calls) == total + 1
    assert {e["ticker"] for e in r2["errores"]} == {"AAPL", "MSFT"}


# ---------- POST /api/radar/{ticker} ----------

def test_radar_add(isolated, monkeypatch):
    c = isolated
    calls, sec_calls = _mocks(monkeypatch)
    assert c.post("/api/radar/TICKERDEMASIADOLARGO").status_code == 400
    assert c.post("/api/radar/NO!").status_code == 400

    r = c.post("/api/radar/zzx")                  # minúsculas aceptadas
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["ticker"] == "ZZX" and body["errores"] == []
    assert calls == ["ZZX"] and sec_calls == ["ZZX"]   # solo ese ticker
    cand = [x for x in c.get("/api/candidates").json()["candidates"]
            if x["ticker"] == "ZZX"]
    assert len(cand) == 1 and cand[0]["source"] == "radar"

    # repetido no duplica el candidato
    assert c.post("/api/radar/ZZX").status_code == 200
    cand2 = [x for x in c.get("/api/candidates").json()["candidates"]
             if x["ticker"] == "ZZX"]
    assert len(cand2) == 1

    item = next(i for i in c.get("/api/radar").json()["items"] if i["ticker"] == "ZZX")
    assert item["en_watchlist"] and item["veredicto"] != "faltan_datos"
