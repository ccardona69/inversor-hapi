"""Pruebas del MVP de Inversor Hapi IA: cálculo, validación, riesgo, decisiones y API.

Las pruebas no dependen de la red: los precios se ingresan manualmente
(el fetch de Yahoo se prueba por separado y de forma tolerante a fallos).
"""
import json
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from app import analysis as AN
from app import db as D
from app import risk as RK
from app import decisions as DE
from app import marketdata as MD
from app import photosync as PS
from app.main import app

client = TestClient(app)

FUND_NVDA_TEST = {  # DATOS DE PRUEBA (no reales): sirven para validar los cálculos
    "revenue": 130_000_000_000, "revenue_growth_pct": 60, "eps": 2.95, "eps_fwd": 4.0,
    "eps_growth_pct": 55, "fcf": 60_000_000_000, "shares_out": 24_500_000_000,
    "debt": 10_000_000_000, "cash": 38_000_000_000, "gross_margin_pct": 75,
    "op_margin_pct": 62, "roic_pct": 90, "ebitda": 86_000_000_000,
    "moat": "Ecosistema CUDA y liderazgo en GPU (dato de prueba)",
    "key_risks": "Ciclicidad, competencia, concentración de clientes (dato de prueba)",
    "next_earnings_date": "2099-01-01",
}


# ---------- unidades ----------

def test_staleness():
    now = datetime.now(timezone.utc)
    assert MD.staleness(now.isoformat())["status"] == "actual"
    assert MD.staleness((now - timedelta(days=3)).isoformat())["status"] == "reciente"
    old = MD.staleness((now - timedelta(days=30)).isoformat())
    assert old["status"] == "desactualizado" and not old["usable_as_current"]
    assert MD.staleness(None)["usable_as_current"] is False


def test_multiples_and_missing():
    m = AN.multiples(200.0, FUND_NVDA_TEST)
    assert m["multiples"]["pe"] == round(200 / 2.95, 1)
    assert m["multiples"]["pe_forward"] == 50.0
    assert "peg" in m["multiples"] and "price_to_fcf" in m["multiples"]
    empty = AN.multiples(200.0, {})
    assert not empty["multiples"] and len(empty["missing"]) >= 4


def test_dcf_scenarios_are_ranges_not_certainty():
    v = AN.valuation_scenarios(200.0, FUND_NVDA_TEST)
    assert v["calculable"]
    p, b, o = (v["escenarios"][k]["valor_estimado_por_accion"] for k in ("pesimista", "base", "optimista"))
    assert p < b < o  # rango, no precio único
    assert v["escenarios"]["base"]["supuestos"]["discount_rate_pct"] == 10.0
    # supuestos modificables
    v2 = AN.valuation_scenarios(200.0, FUND_NVDA_TEST, {"discount_rate_pct": 14.0})
    assert v2["escenarios"]["base"]["valor_estimado_por_accion"] < b
    # sin FCF no se inventa nada
    v3 = AN.valuation_scenarios(200.0, {})
    assert not v3["calculable"] and v3["faltantes"]


def test_risk_concentration_and_correlation():
    positions = [
        {"ticker": "NVDA", "sector": None, "market_value": 313.49, "invested": 335.37},
        {"ticker": "MSFT", "sector": None, "market_value": 107.19, "invested": 118.44},
    ]
    r = RK.portfolio_risk(positions, 0, {})
    nvda_w = next(w for w in r["pesos"] if w["ticker"] == "NVDA")["peso_pct"]
    assert 74 < nvda_w < 75.1  # ~74.52 % según el reporte de Hapi
    assert r["nivel_concentracion"] == "alta"
    assert any("NO es diversificación suficiente" in c for c in r["correlacion"])
    assert any(b["tipo"] == "posicion" for b in r["incumplimientos"])  # excede 25 % por defecto


def test_decision_engine_never_uses_avg_cost_as_reason():
    ctx = {"ticker": "NVDA", "price": 202.81, "price_status": "actual", "qty": 1.54575,
           "market_value": 313.49, "invested": 335.37, "avg_cost": 216.96, "unrealized_pl": -21.88,
           "weight_pct": 74.52, "max_position_pct": 25, "margin_of_safety_pct": None,
           "fundamentals": False, "has_thesis": False, "technical": None, "profile_complete": False}
    d = DE.evaluate_position(ctx)
    assert d["decision_propuesta"] in ("reducir", "esperar")
    assert d["nivel_confianza"] == "baja"  # perfil incompleto -> informativo
    assert "efectivo" in d["pregunta_obligatoria"]
    joined = " ".join(d["argumentos"])
    assert "informativa" in joined
    # checklist de promediar presente porque está en pérdida
    assert d["checklist_promediar"] and len(d["checklist_promediar"]) == 10
    # ningún argumento usa el costo promedio como razón
    assert "costo promedio" not in joined.lower() or "no" in joined.lower()


# ---------- API ----------

@pytest.fixture(scope="module")
def session():
    return client


def test_portfolio_positions_and_validation(session):
    c = session
    src = "Hapi — captura de prueba (pendiente de verificación)"
    for p in [
        {"ticker": "NVDA", "name": "NVIDIA", "qty": 1.54575, "invested": 335.37,
         "avg_cost": 216.96, "hapi_value": 313.49, "hapi_pl": -21.88,
         "hapi_return_pct": -6.52, "source": src},
        {"ticker": "MSFT", "name": "Microsoft", "qty": 0.27219, "invested": 118.44,
         "avg_cost": 435.14, "hapi_value": 107.19, "hapi_pl": -11.25,
         "hapi_return_pct": -9.50, "source": src},
    ]:
        assert c.post("/api/positions", json=p).status_code == 200
    pf = c.get("/api/portfolio").json()
    assert {p["ticker"] for p in pf["positions"]} == {"NVDA", "MSFT"}
    assert abs(pf["totals"]["invertido"] - 453.81) < 0.01
    assert pf["totals"]["valor_actual"] is None and pf["totals"]["resultado"] is None
    assert set(pf["totals"]["sin_precio_vigente"]) == {"NVDA", "MSFT"}
    # La foto conserva los valores por fila, pero no se suman como valor actual.
    nvda = next(p for p in pf["positions"] if p["ticker"] == "NVDA")
    assert nvda["hapi_value"] == 313.49 and "verificar" in nvda["price_info"]["fuente"]

    val = c.get("/api/validate").json()["report"]
    nvda_v = next(r for r in val if r["ticker"] == "NVDA")
    assert any("Comisiones" in p for p in nvda_v["pendientes"])
    assert any("Costo promedio derivado" in x for x in nvda_v["calculados"])


def test_manual_price_and_analysis(session):
    c = session
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for tk, price in (("NVDA", 202.81), ("MSFT", 393.81)):
        r = c.post("/api/prices/manual", json={"ticker": tk, "price": price, "asof": now,
                                               "source": "prueba manual"})
        assert r.status_code == 200
    c.put("/api/fundamentals/NVDA", json={"data": FUND_NVDA_TEST, "source": "datos de prueba", "asof": "2026-07-01"})
    rep = c.post("/api/analysis/NVDA", json={}).json()
    assert rep["ticker"] == "NVDA" and rep["precio_actual"]["valor"] == 202.81
    assert rep["decision"]["decision_propuesta"] in ("reducir", "mantener", "esperar", "agregar_gradualmente")
    assert rep["decision"]["pregunta_obligatoria"]
    assert rep["valoracion"]["escenarios"]["base"]["supuestos"]
    assert rep["peso_en_cartera_pct"] and rep["peso_en_cartera_pct"] > 70
    # sobre-concentración + sin perfil completo -> reduce o espera, con confianza baja
    assert rep["decision"]["nivel_confianza"] == "baja"
    assert "disclaimer" in rep

    # registrar la decisión del usuario: nunca ejecuta
    r = c.post(f"/api/decisions/{rep['decision_id']}/record", json={"choice": "mantener", "authorized": True})
    assert "ejecución la realizas tú" in r.json()["detail"]


def test_analysis_requires_price(session):
    r = session.post("/api/analysis/ZZZZ", json={})
    assert r.status_code == 400


def test_journal_requires_thesis_for_trades(session):
    c = session
    r = c.post("/api/journal", json={"ticker": "NVDA", "action": "comprar", "tesis": ""})
    assert r.status_code == 400  # sin tesis/riesgos/invalidación no se registra una operación
    r = c.post("/api/journal", json={
        "ticker": "NVDA", "action": "revision",
        "tesis": "Liderazgo en aceleradores (prueba)", "riesgos": "ciclo, competencia",
        "condicion_invalidacion": "pérdida de cuota sostenida", "review_date": "2020-01-01"})
    assert r.status_code == 200
    jid = r.json()["id"]
    # la fecha de revisión vencida genera alerta de acción pendiente
    al = c.get("/api/alerts").json()["alerts"]
    assert any(a["type"] == "revision_tesis" for a in al)
    r = c.post(f"/api/journal/{jid}/evaluate", json={"que_ocurrio": "estable", "suerte_o_proceso": "proceso"})
    assert r.status_code == 200


def test_alerts_concentration_and_profile(session):
    al = session.get("/api/alerts").json()["alerts"]
    assert any(a["type"] == "limite_excedido" for a in al)      # NVDA > 25 %
    assert any(a["type"] == "correlacion" for a in al)          # NVDA+MSFT tecnología/IA
    assert any(a["type"] == "perfil" for a in al)               # perfil incompleto


def test_profile_completion_changes_alert(session):
    c = session
    prof = {f: "1" for f in DE.RISK_PROFILE_FIELDS}
    r = c.put("/api/profile", json=prof)
    assert r.json()["complete"]
    al = c.get("/api/alerts").json()["alerts"]
    assert not any(a["type"] == "perfil" for a in al)


def test_candidates_ranking(session):
    c = session
    c.post("/api/candidates", json={"ticker": "VTI", "name": "ETF total (prueba)", "source": "análisis propio",
                                    "data": {"calidad": 8, "crecimiento": 5, "valoracion": 7, "margen_seguridad": 6,
                                             "solidez": 9, "riesgo": 2, "tesis": "diversificación (prueba)"}})
    c.post("/api/candidates", json={"ticker": "XYZ", "name": "especulativa (prueba)", "source": "análisis propio",
                                    "data": {"calidad": 3, "crecimiento": 9, "valoracion": 2, "margen_seguridad": 1,
                                             "solidez": 2, "riesgo": 9}})
    ranked = c.get("/api/candidates").json()["candidates"]
    assert ranked[0]["ticker"] == "VTI"  # mejor riesgo/retorno según los datos del usuario


def test_dashboard_api(session):
    d = session.get("/api/dashboard").json()
    assert d["risk"]["nivel_concentracion"] == "alta"
    assert d["calidad_datos"]


@pytest.mark.red
def test_yahoo_fetch_tolerant():
    """Prueba de integración tolerante: si no hay red, debe fallar con mensaje claro."""
    try:
        q = MD.fetch_quote("NVDA")
        assert q["price"] > 0 and q["source"].startswith("Yahoo") and q["asof"]
    except MD.MarketDataError as e:
        assert "manual" in str(e)


# ---------- sincronización por foto (IA de visión) ----------

LUNA_TEST_ENV = {  # configuración de prueba: Azure Foundry estilo Responses
    "INVERSOR_AI_API_KEY": "clave-de-prueba", "INVERSOR_AI_MODEL": "gpt-5.6-luna",
    "INVERSOR_AI_BASE_URL": "https://recurso.services.ai.azure.com/foundry/openai/v1",
    "INVERSOR_AI_API_STYLE": "responses",
}


def test_photosync_normalize_rows():
    rows, omitidas = PS.normalize_rows([
        {"ticker": "nvda", "qty": "1.54575", "avg_cost": "216.96", "value": 313.49,
         "pl": "-21.88", "pl_pct": "no visible", "invested": None},
        {"ticker": "", "qty": 5},                          # omitida: sin ticker
        {"ticker": "MSFT", "qty": 0},                      # omitida: cantidad 0
        "texto suelto",                                    # omitida: no es fila
    ])
    assert len(rows) == 1 and len(omitidas) == 3
    r = rows[0]
    assert r["ticker"] == "NVDA" and r["qty"] == 1.54575
    assert r["hapi_pl"] == -21.88 and r["hapi_value"] == 313.49
    assert r["invested"] is None and r["hapi_return_pct"] is None  # lo no visible no se inventa


def test_photosync_analyze_responses_style(fake_client):
    reply = json.dumps({"posiciones": [
        {"ticker": "NVDA", "name": "NVIDIA", "qty": 1.54575, "avg_cost": 216.96,
         "invested": 335.37, "value": 313.49, "pl": -21.88, "pl_pct": -6.52}]})
    # dentro de un fence markdown, como suelen responder los modelos
    fake = fake_client({"output": [{"content": [{"type": "output_text",
                                                 "text": "```json\n" + reply + "\n```"}]}]})
    out = PS.analyze("falsobase64", "image/jpeg", env=LUNA_TEST_ENV, client=fake)
    assert out["rows"][0]["ticker"] == "NVDA" and out["model"] == "gpt-5.6-luna"
    assert out["cash"] is None
    url, headers, cuerpo = fake.calls[0]
    assert url.endswith("/foundry/openai/v1/responses")
    assert headers["api-key"] == "clave-de-prueba"
    assert cuerpo["max_output_tokens"] == 2048
    assert cuerpo["input"][0]["content"][1]["type"] == "input_image"
    assert cuerpo["input"][0]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")


def test_photosync_analyze_chat_style_and_errors(fake_client):
    reply = json.dumps({"posiciones": []})
    fake = fake_client({"choices": [{"message": {"content": reply}}]})
    env = dict(LUNA_TEST_ENV, INVERSOR_AI_API_STYLE="chat",
               INVERSOR_AI_BASE_URL="https://recurso.openai.azure.com")
    out = PS.analyze("falsobase64", "image/jpeg", env=env, client=fake)
    assert out["rows"] == []
    url = fake.calls[0][0]
    assert "/openai/deployments/gpt-5.6-luna/chat/completions" in url and "api-version=" in url
    # sin configuración, error claro (no se intenta la red)
    with pytest.raises(PS.PhotoSyncError):
        PS.analyze("x", "image/jpeg", env={}, client=fake)
    # respuesta sin JSON interpretable
    malo = fake_client({"output": [{"content": [{"type": "output_text", "text": "no soy json"}]}]})
    with pytest.raises(PS.PhotoSyncError):
        PS.analyze("x", "image/jpeg", env=LUNA_TEST_ENV, client=malo)


def test_photo_endpoints(session, monkeypatch):
    c = session
    # estado: la configuración de prueba no debe filtrarse
    st = c.get("/api/hapi/photo/status").json()
    assert "configured" in st and "api_key" not in json.dumps(st)
    # analizar: imagen vacía -> 400; fallo de la IA -> 502; éxito -> filas
    assert c.post("/api/hapi/photo/analyze", json={}).status_code == 400
    monkeypatch.setattr(PS, "analyze", lambda *a, **k: (_ for _ in ()).throw(PS.PhotoSyncError("boom")))
    assert c.post("/api/hapi/photo/analyze", json={"image_b64": "abc"}).status_code == 502
    rows = [{"ticker": "KO", "name": "Coca-Cola (prueba)", "qty": 3, "avg_cost": 60.0,
             "invested": 180.0, "hapi_value": 192.0, "hapi_pl": 12.0, "hapi_return_pct": 6.67},
            {"ticker": "", "qty": 2}]
    monkeypatch.setattr(PS, "analyze", lambda *a, **k: {"rows": rows, "omitted": [], "cash": 173.35, "model": "prueba"})
    r = c.post("/api/hapi/photo/analyze", json={"image_b64": "abc"})
    assert r.status_code == 200 and r.json()["rows"][0]["ticker"] == "KO"
    # guardar: guarda lo confirmado, omite lo inválido, actualiza efectivo y marca la fuente
    r = c.post("/api/hapi/photo/save", json={"rows": rows, "cash": 173.35})
    assert r.status_code == 200 and r.json()["importadas"] == ["KO"] and r.json()["cash"] == 173.35
    pf = c.get("/api/portfolio").json()
    ko = next(p for p in pf["positions"] if p["ticker"] == "KO")
    assert "captura analizada por IA" in ko["source"] and not ko["verified"]
    assert ko["hapi_value"] == 192.0 and abs(ko["invested"] - 180.0) < 0.01
    assert abs(pf["cash"] - 173.35) < 0.01
    assert c.post("/api/hapi/photo/save", json={"rows": []}).status_code == 400


def test_delete_all(session):
    r = session.post("/api/settings/delete_all", json={"confirm": "ELIMINAR"})
    assert r.status_code == 200
    assert session.get("/api/portfolio").json()["positions"] == []


# ---------- pruebas con BD aislada (cartera en un paso, cambio del día) ----------

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "isolated.db"))
    D.init_db()
    return TestClient(app)


def _price(ticker, price, day_change_pct=None):
    conn = D.get_db()
    conn.execute("INSERT INTO prices (ticker, price, currency, asof, source, day_change_pct, created_at) "
                 "VALUES (?,?,?,?,?,?,?)",
                 (ticker, price, "USD", datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "prueba", day_change_pct, D.now()))
    conn.commit()
    conn.close()


def test_portfolio_cambio_dia(isolated):
    c = isolated
    c.post("/api/positions", json={"ticker": "AAA", "qty": 2, "invested": 180})
    c.post("/api/positions", json={"ticker": "BBB", "qty": 1, "invested": 90})
    _price("AAA", 110.0, 10.0)
    _price("BBB", 100.0, None)  # una posición sin cambio diario: no calculable
    t = c.get("/api/portfolio").json()["totals"]
    assert t["valor_actual"] == 320 and t["cambio_dia"] is None and t["cambio_dia_pct"] is None
    _price("BBB", 100.0, 5.0)
    t = c.get("/api/portfolio").json()["totals"]
    prev = 220 / 1.10 + 100 / 1.05
    assert abs(t["cambio_dia"] - round(320 - prev, 2)) < 0.01
    assert abs(t["cambio_dia_pct"] - round((320 / prev - 1) * 100, 2)) < 0.01


def test_photo_save_confirmed_and_replace_all(isolated):
    c = isolated
    c.post("/api/positions", json={"ticker": "OLD", "qty": 1, "invested": 50})
    rows = [{"ticker": "NEW", "qty": 2, "avg_cost": 60.0}, {"ticker": "", "qty": 2}]
    # reemplazar sin confirmar la revisión: 400 y nada cambia
    r = c.post("/api/hapi/photo/save", json={"rows": rows, "replace_all": True})
    assert r.status_code == 400
    assert {p["ticker"] for p in c.get("/api/portfolio").json()["positions"]} == {"OLD"}
    # reemplazar sin filas válidas: 400 y nada se borra
    r = c.post("/api/hapi/photo/save", json={"rows": [{"ticker": "", "qty": 2}],
                                           "confirmed": True, "replace_all": True})
    assert r.status_code == 400
    assert {p["ticker"] for p in c.get("/api/portfolio").json()["positions"]} == {"OLD"}
    # confirmado + reemplazo: NEW queda verificada y OLD se reporta eliminada
    r = c.post("/api/hapi/photo/save", json={"rows": rows, "confirmed": True,
                                             "replace_all": True, "cash": 10})
    assert r.status_code == 200
    d = r.json()
    assert d["importadas"] == ["NEW"] and d["eliminadas"] == ["OLD"] and d["cash"] == 10
    positions = c.get("/api/portfolio").json()["positions"]
    assert {p["ticker"] for p in positions} == {"NEW"}
    assert positions[0]["verified"]


def test_verify_all_positions(isolated):
    c = isolated
    c.post("/api/positions", json={"ticker": "AAA", "qty": 1, "invested": 10})
    c.post("/api/positions", json={"ticker": "BBB", "qty": 1, "invested": 10})
    r = c.post("/api/positions/verify_all")
    assert r.status_code == 200 and r.json()["confirmadas"] == 2
    assert all(p["verified"] for p in c.get("/api/portfolio").json()["positions"])
    assert c.post("/api/positions/verify_all").json()["confirmadas"] == 0
