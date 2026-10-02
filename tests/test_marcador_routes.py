"""Fase 1: rutas del marcador, la alcancía, los avisos y la regla del plan de Luna."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_provider as AP
from app import db as D
from app import flowsync as FS
from app import marketdata as MD
from app.main import app

client = TestClient(app)

# Los 9 depósitos reales del historial de Hapi (aceptación): neto $949.41.
DEPOSITOS = [
    {"kind": "deposito", "amount_usd": 9, "at": "2025-12-26"},
    {"kind": "deposito", "amount_usd": 76.71, "at": "2026-01-07"},
    {"kind": "deposito", "amount_usd": 72, "at": "2026-01-26"},
    {"kind": "deposito", "amount_usd": 105.44, "at": "2026-02-23"},
    {"kind": "deposito", "amount_usd": 85.76, "at": "2026-04-15"},
    {"kind": "deposito", "amount_usd": 13, "at": "2026-05-21"},
    {"kind": "deposito", "amount_usd": 301, "at": "2026-08-24"},
    {"kind": "deposito", "amount_usd": 221.50, "at": "2026-08-25"},
    {"kind": "deposito", "amount_usd": 65, "at": "2026-09-08"},
]


@pytest.fixture(autouse=True)
def limpio():
    """Las pruebas comparten una BD: cada una arranca sin movimientos,
    posiciones, precios, efectivo, ajustes ni diario."""
    conn = D.get_db()
    uid = D.local_user_id(conn)
    conn.execute("DELETE FROM contributions WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM positions WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM cash WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM settings WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM journal WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM prices")
    conn.commit()
    conn.close()
    yield


def _confirm(rows, **kw):
    return client.post("/api/flows/confirm", json={"rows": rows, "reviewed": True, **kw})


def _draft(text):
    r = client.post("/api/flows/draft", json={"text": text})
    assert r.status_code == 200, r.json()
    return r.json()


def test_nueve_depositos_marcador_sin_red():
    r = _confirm(DEPOSITOS)
    assert r.status_code == 200 and r.json()["imported"] == 9
    mc = client.get("/api/marcador")
    assert mc.status_code == 200
    m = mc.json()["marcador"]
    assert m["depositado_neto"] == 949.41 and m["n_depositos"] == 9
    # Yahoo bloqueado en pruebas: sin tc del día → costos por tarifa estimada.
    assert m["costos_deposito"] == 27.0 and m["costos_etiqueta"] == "ESTIMACIÓN"
    assert m["puesto_bolsillo"] == 976.41
    # No hay posiciones ni efectivo registrado: cero no es un valor de cartera confirmado.
    assert m["valor_actual"] is None and m["resultado_real"] is None
    assert client.get("/api/portfolio").json()["cash_registrado"] is False
    assert mc.json()["fuentes"]["valor_actual"]["fecha"] is None
    assert mc.json()["fantasma"] is None  # sin dato, no 500
    assert mc.json()["alcancia"]["ahorro_estimado"] is True


def test_marcador_fecha_es_la_cotizacion_mas_antigua_usada():
    _confirm(DEPOSITOS[:1])
    older = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    newer = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for ticker, price, asof in (("AAA", 10, older), ("BBB", 20, newer)):
        assert client.post("/api/positions", json={"ticker": ticker, "qty": 1,
                                                    "source": "captura"}).status_code == 200
        assert client.post(f"/api/positions/{ticker}/verify").status_code == 200
        assert client.post("/api/prices/manual", json={"ticker": ticker, "price": price,
                            "asof": asof, "source": "fuente de prueba"}).status_code == 200
    mc = client.get("/api/marcador").json()
    assert mc["marcador"]["valor_actual"] == 30
    assert mc["fuentes"]["valor_actual"]["fecha"] == older
    assert mc["fuentes"]["valor_actual"]["efectivo_pendiente"] is True


def test_posicion_sin_verificar_no_entra_al_marcador():
    """Una captura analizada por IA queda verified=0 hasta que el usuario la
    confirma: no puede alimentar una línea HECHO del marcador."""
    _confirm(DEPOSITOS[:1])
    assert client.post("/api/positions", json={"ticker": "AAA", "qty": 1,
                                                "source": "captura"}).status_code == 200
    assert client.post("/api/prices/manual", json={"ticker": "AAA", "price": 10,
                        "asof": datetime.now(timezone.utc).isoformat(),
                        "source": "fuente de prueba"}).status_code == 200
    mc = client.get("/api/marcador").json()
    assert mc["fuentes"]["valor_actual"]["sin_verificar"] == ["AAA"]
    assert mc["marcador"]["valor_actual"] is None  # sin valor verificado: sin dato
    # Tras verificarla sí entra.
    assert client.post("/api/positions/AAA/verify").status_code == 200
    mc = client.get("/api/marcador").json()
    assert mc["marcador"]["valor_actual"] == 10
    assert mc["fuentes"]["valor_actual"]["sin_verificar"] == []


def test_efectivo_en_moneda_incompatible_impide_resultado_de_bolsillo():
    _confirm(DEPOSITOS[:1])
    assert client.post("/api/positions", json={"ticker": "AAA", "qty": 1}).status_code == 200
    assert client.post("/api/positions/AAA/verify").status_code == 200
    assert client.post("/api/prices/manual", json={"ticker": "AAA", "price": 10,
                        "asof": datetime.now(timezone.utc).isoformat(),
                        "source": "fuente de prueba"}).status_code == 200
    conn = D.get_db()
    try:
        uid = D.local_user_id(conn)
        conn.execute("INSERT INTO cash (user_id, amount, currency, updated_at) VALUES (?, 5, 'EUR', ?)",
                     (uid, D.now()))
        conn.commit()
    finally:
        conn.close()
    mc = client.get("/api/marcador").json()
    assert mc["marcador"]["valor_actual"] is None
    assert mc["marcador"]["resultado_real"] is None
    assert mc["fuentes"]["valor_actual"]["fecha"] is None


def test_efectivo_registrado_sin_posiciones_si_tiene_fuente_y_fecha():
    _confirm(DEPOSITOS[:1])
    assert client.put("/api/cash", json={"amount": 8, "currency": "USD"}).status_code == 200
    assert client.get("/api/portfolio").json()["cash_registrado"] is True
    mc = client.get("/api/marcador").json()
    assert mc["marcador"]["valor_actual"] == 8
    assert mc["fuentes"]["valor_actual"]["fuente"] == "efectivo registrado en Cartera"
    assert mc["fuentes"]["valor_actual"]["fecha"]
    assert mc["fuentes"]["valor_actual"]["efectivo_pendiente"] is False


def test_guardar_80_soles_no_mueve_el_marcador():
    _confirm(DEPOSITOS)
    draft = _draft("guardé 80 soles")
    assert draft["rows"][0]["kind"] == "ahorro_soles"
    assert draft["rows"][0]["posible_duplicado"] is False
    r = _confirm(draft["rows"])
    assert r.status_code == 200 and r.json()["imported"] == 1
    mc = client.get("/api/marcador").json()
    assert mc["marcador"]["depositado_neto"] == 949.41
    assert mc["alcancia"]["progreso"] == 80


def test_deposito_480_con_llegada_descuenta_la_alcancia(monkeypatch):
    def fake_history(ticker, rng="1y"):
        if ticker == "PEN=X":
            return {"rows": [{"date": "2020-01-02", "close": 3.55, "adjclose": 3.55}],
                    "source": "Yahoo Finance PEN=X (prueba)"}
        return {"rows": [{"date": "2020-01-02", "close": 100, "adjclose": 100},
                         {"date": "2099-01-02", "close": 120, "adjclose": 120}],
                "source": "Yahoo Finance SPY (prueba)"}
    monkeypatch.setattr(MD, "fetch_history", fake_history)
    _confirm([{"kind": "ahorro_soles", "soles_amount": 500, "at": "2026-09-01"}])
    draft = _draft("deposité 480 soles y llegaron 132.50")
    assert draft["rows"][0]["fx_rate"] == round(480 / 132.5, 4)
    r = _confirm(draft["rows"])
    assert r.status_code == 200 and r.json()["imported"] == 1
    mc = client.get("/api/marcador").json()
    assert mc["alcancia"]["progreso"] == 20  # el sobrante queda en la alcancía
    dep = next(d for d in mc["marcador"]["costos_detalle"] if d["soles_amount"] == 480)
    assert dep["valor"] == pytest.approx(2.71, abs=0.005)
    assert dep["etiqueta"] == "CÁLCULO" and dep["tc_fuente"].startswith("Yahoo")
    assert mc["fantasma"] is not None and "diferencia" in mc["fantasma"]


def test_historial_dos_veces_duplicados():
    assert _confirm(DEPOSITOS).status_code == 200
    r = _confirm(DEPOSITOS)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "duplicad" in detail["message"] and len(detail["duplicates"]) == 9
    assert len(client.get("/api/flows").json()["rows"]) == 9  # nada se insertó
    r = _confirm(DEPOSITOS, allow_duplicates=True)
    assert r.status_code == 200 and r.json()["imported"] == 9
    assert len(client.get("/api/flows").json()["rows"]) == 18


def test_flows_list_delete_y_validaciones(monkeypatch):
    def _sin_ia(text, **kwargs):
        raise FS.FlowSyncError("IA no disponible en la prueba")
    monkeypatch.setattr(FS, "analyze_text", _sin_ia)
    _confirm(DEPOSITOS[:1])
    rows = client.get("/api/flows").json()["rows"]
    assert len(rows) == 1 and rows[0]["kind"] == "deposito"
    assert client.delete(f"/api/flows/{rows[0]['id']}").status_code == 200
    assert client.get("/api/flows").json()["rows"] == []
    assert client.delete("/api/flows/999999").status_code == 404
    assert client.post("/api/flows/confirm",
                       json={"rows": [{"kind": "deposito", "amount_usd": 9, "at": "2025-12-26"}]}
                       ).status_code == 400  # falta reviewed
    assert client.post("/api/flows/draft", json={"text": "hola"}).status_code == 400
    bad = client.post("/api/flows/draft", json={"text": "texto largo que no es historial "
                                                  "de movimientos de hapi"})
    assert bad.status_code == 502 and "IA no disponible" in str(bad.json()["detail"])


def test_actividad_y_w8ben_actualizan_ajustes_y_avisan():
    hace_60 = (date.today() - timedelta(days=60)).isoformat()
    d, m_, y = hace_60[8:10], hace_60[5:7], hace_60[:4]
    draft = _draft(f"entré a Hapi el {d}/{m_}/{y}")
    assert draft["rows"][0]["kind"] == "actividad"
    r = _confirm(draft["rows"])
    assert r.status_code == 200 and "last_hapi_check" in r.json()["settings_updated"]
    vence = (date.today() + timedelta(days=10)).isoformat()
    draft = _draft(f"mi W-8BEN vence el {vence}")
    assert draft["rows"][0] == {"kind": "w8ben", "at": vence}
    _confirm(draft["rows"])
    tipos = {a["type"] for a in client.get("/api/marcador").json()["avisos"]}
    assert "hapi_inactividad" in tipos and "w8ben" in tipos
    # La entrada reciente a Hapi apaga el aviso de inactividad.
    _confirm([{"kind": "actividad", "at": date.today().isoformat()}])
    tipos = {a["type"] for a in client.get("/api/marcador").json()["avisos"]}
    assert "hapi_inactividad" not in tipos


def test_aviso_meta_alcancia():
    _confirm([{"kind": "ahorro_soles", "soles_amount": 500,
               "at": date.today().isoformat()}])
    avisos = client.get("/api/marcador").json()["avisos"]
    assert any(a["type"] == "alcancia_meta" for a in avisos)


def test_endpoint_alcancia_propio():
    """GET /api/alcancia (§13): la misma fuente que la tarjeta, sin red."""
    _confirm([{"kind": "ahorro_soles", "soles_amount": 160, "at": "2026-09-01"}])
    r = client.get("/api/alcancia")
    assert r.status_code == 200
    a = r.json()
    assert a["progreso"] == 160 and a["meta_soles"] == pytest.approx(480, abs=1)
    assert a["optimo_soles"] == pytest.approx(639.5, abs=1)
    assert a["meses_por_deposito"] == pytest.approx(6, abs=0.1)
    assert a["ahorro_estimado"] is True


def test_delete_all_borra_contributions():
    _confirm(DEPOSITOS)
    assert len(client.get("/api/flows").json()["rows"]) == 9
    r = client.post("/api/settings/delete_all", json={"confirm": "ELIMINAR"})
    assert r.status_code == 200
    assert client.get("/api/flows").json()["rows"] == []


def test_luna_regla_del_plan_sin_proveedor(monkeypatch):
    def _prohibido(*args, **kwargs):
        pytest.fail("la regla del plan no debe llamar al proveedor de IA")
    monkeypatch.setattr(AP, "request", _prohibido)
    r = client.post("/api/assistant/ask", json={"question": "¿compro NVDA?"})
    assert r.status_code == 200
    d = r.json()
    assert d["model"] == "regla-del-plan" and d["plan_guard"] is True
    assert "ETF" in d["answer"] and "NVDA" in d["answer"]
    assert "¿cambió la empresa o solo el precio?" in d["answer"]
    # El seguimiento guarda la respuesta del usuario en el Diario.
    r2 = client.post("/api/assistant/ask", json={
        "question": "Cambió el precio, la empresa sigue igual",
        "history": [{"role": "user", "content": "¿compro NVDA?"},
                    {"role": "assistant", "content": d["answer"]}]})
    assert r2.status_code == 200 and r2.json()["model"] == "regla-del-plan"
    entries = client.get("/api/journal").json()["entries"]
    assert entries and entries[0]["ticker"] == "NVDA"
    assert entries[0]["action"] == "revision"
    assert "Cambió el precio, la empresa sigue igual" in entries[0]["data"]["tesis"]


def test_luna_compra_de_etf_no_activa_la_regla(monkeypatch):
    llamadas = []
    def fake_ask(question, context, history=None):
        llamadas.append(question)
        return {"answer": "El ETF encaja en el plan.", "model": "luna-prueba",
                "asof": "hoy"}
    monkeypatch.setattr("app.ai_assistant.ask", fake_ask)
    r = client.post("/api/assistant/ask", json={"question": "¿compro VOO?"})
    assert r.json()["answer"] == "El ETF encaja en el plan."
    assert llamadas == ["¿compro VOO?"]


# ---------- ficha de brecha y ETF del plan (solo lectura / ajuste) ----------

def test_brecha_endpoint_sin_escrituras():
    """GET /api/brecha calcula con el efectivo real y no escribe nada."""
    _confirm(DEPOSITOS)
    client.put("/api/cash", json={"amount": 135})
    conn = D.get_db(); uid = D.local_user_id(conn)
    n0 = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
          for t in ("contributions", "journal", "decisions", "settings")}
    conn.close()
    r = client.get("/api/brecha")
    assert r.status_code == 200
    d = r.json()
    assert d["base"] == "posiciones" and d["meta_pct"] == 50
    assert d["evaluable"] is True                    # cartera vacía: evaluable
    assert d["a_invertir_usd"] == 135 and d["a_etf_usd"] == 67.5
    assert d["etf_plan"] == "SPY" and "proyeccion" in d
    conn = D.get_db()
    n1 = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
          for t in ("contributions", "journal", "decisions", "settings")}
    conn.close()
    assert n0 == n1                                     # ni un default persistido


def test_brecha_con_cartera_y_aporte_planificado():
    client.post("/api/positions", json={"ticker": "AAA", "qty": 10, "invested": 900})
    client.post("/api/prices/manual",
                json={"ticker": "AAA", "price": 100.0, "asof": "2026-09-30",
                      "source": "prueba"})
    r = client.get("/api/brecha?aporte_nuevo_usd=200")
    assert r.status_code == 200
    d = r.json()
    assert d["valor_base_usd"] == 1000.0 and d["etf_pct"] == 0.0
    assert d["brecha_usd"] == 500.0                     # 50 % de 1000 (venta)
    assert d["dinero_nuevo_para_meta_usd"] == 1000.0    # por aportes: el doble
    assert d["a_etf_usd"] == 200.0 and d["libre_usd"] == 0.0


def test_brecha_posiciones_sin_precio_no_evaluable():
    """Posiciones registradas sin ningún precio: la brecha no se puede
    evaluar y la ficha va fail-closed (todo al ETF), nunca «en meta»."""
    client.post("/api/positions", json={"ticker": "AAA", "qty": 10, "invested": 900})
    client.put("/api/cash", json={"amount": 100})
    d = client.get("/api/brecha").json()
    assert d["evaluable"] is False and d["en_meta"] is False
    assert d["a_etf_usd"] == 100.0 and d["libre_usd"] == 0.0
    assert d["etf_pct_despues"] is None
    assert any("no evaluable" in a for a in d["avisos"])


def test_plan_put_valida_etf_conocido():
    assert client.put("/api/plan", json={"etf_plan": "VOO"}).status_code == 200
    assert client.get("/api/settings").json()["etf_plan"] == "VOO"
    assert client.put("/api/plan", json={"etf_plan": "NVDA"}).status_code == 400
    assert client.put("/api/plan", json={"etf_plan": "QQQ"}).status_code == 400


def test_draft_deposito_incompleto_marca_costo_estimado():
    d = _draft("deposité S/ 500")
    row = next(r for r in d["rows"] if r["kind"] == "deposito")
    assert "costo_nota" in row and "ESTIMACIÓN" in row["costo_nota"]
    d = _draft("deposité S/ 500 y llegaron $135")
    row = next(r for r in d["rows"] if r["kind"] == "deposito")
    assert "costo_nota" not in row                     # tiene los dos datos


def test_marcador_expone_cobertura_costo_real():
    _confirm(DEPOSITOS)                                # 9 depósitos sin soles
    m = client.get("/api/marcador").json()["marcador"]
    assert m["cobertura_costo_real"] == {"con_calculo": 0, "total": 9}
