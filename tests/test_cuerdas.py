"""Cuerdas de Ulises: aflojar límites o perfil espera 7 días con motivo;
endurecer (y el primer valor) aplica al instante. Sin esquema nuevo: los
lotes pendientes viven en settings y quedan anotados en el Diario."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import cuerdas as CU
from app import db as D
from app.main import app


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "cuerdas.db"))
    D.init_db()
    return TestClient(app)


def _journal(c):
    return c.get("/api/journal").json()["entries"]


def _tesis(entry):
    return entry["data"]["tesis"]


# ---------- límites ----------


def test_endurecer_aplica_al_instante(isolated):
    r = isolated.put("/api/limits", json={"max_position_pct": 20})
    assert r.status_code == 200
    d = r.json()
    assert d["aplicados"] == {"max_position_pct": 20}
    assert d["pendientes"] is None
    assert d["limits"]["max_position_pct"] == 20
    assert isolated.get("/api/settings").json()["pendientes"] is None


def test_aflojar_sin_motivo_rechaza(isolated):
    isolated.put("/api/limits", json={"max_position_pct": 20})
    r = isolated.put("/api/limits", json={"max_position_pct": 30})
    assert r.status_code == 400
    assert "motivo" in r.json()["detail"]
    # nada quedó pendiente ni aplicado
    assert isolated.get("/api/settings").json()["limits"]["max_position_pct"] == 20


def test_aflojar_con_motivo_queda_pendiente_con_diario(isolated):
    isolated.put("/api/limits", json={"max_position_pct": 20})
    r = isolated.put("/api/limits", json={"max_position_pct": 30,
                                          "motivo": "quiero entrar a NVDA"})
    assert r.status_code == 200
    d = r.json()
    assert d["pendientes"]["cambios"] == {"max_position_pct": 30}
    assert d["pendientes"]["motivo"] == "quiero entrar a NVDA"
    assert d["limits"]["max_position_pct"] == 20       # efectivo: sin cambio
    # constancia en el Diario con la fecha de efectividad
    assert any("afloja" in _tesis(e) and "Efectivo desde" in _tesis(e)
               for e in _journal(isolated))
    # expuesto también en GET /api/settings
    assert isolated.get("/api/settings").json()["pendientes"]["cambios"]["max_position_pct"] == 30


def test_lote_madurado_actualiza_el_valor_efectivo(isolated, monkeypatch):
    isolated.put("/api/limits", json={"max_position_pct": 20})
    isolated.put("/api/limits", json={"max_position_pct": 30, "motivo": "prueba"})
    ahora = datetime.now(timezone.utc)
    monkeypatch.setattr(CU, "_now", lambda: ahora + timedelta(days=8))
    # cualquier PUT promueve el lote vencido
    isolated.put("/api/limits", json={"positions_target": 4})
    assert isolated.get("/api/settings").json()["limits"]["max_position_pct"] == 30
    assert isolated.get("/api/settings").json()["pendientes"] is None


def test_endurecer_la_misma_clave_la_saca_del_lote(isolated):
    isolated.put("/api/limits", json={"max_position_pct": 20})
    isolated.put("/api/limits", json={"max_position_pct": 30, "motivo": "prueba"})
    r = isolated.put("/api/limits", json={"max_position_pct": 18})
    d = r.json()
    assert d["aplicados"] == {"max_position_pct": 18}
    assert isolated.get("/api/settings").json()["pendientes"] is None
    assert d["limits"]["max_position_pct"] == 18


def test_nueva_peticion_que_afloja_reinicia_el_lote(isolated):
    isolated.put("/api/limits", json={"max_position_pct": 20})
    isolated.put("/api/limits", json={"max_position_pct": 30, "motivo": "uno"})
    r = isolated.put("/api/limits", json={"max_sector_pct": 45, "motivo": "dos"})
    pend = r.json()["pendientes"]
    assert pend["cambios"] == {"max_sector_pct": 45} and pend["motivo"] == "dos"


def test_cancelar_lote(isolated):
    assert isolated.delete("/api/limits/pendientes").status_code == 404
    isolated.put("/api/limits", json={"max_position_pct": 20})
    isolated.put("/api/limits", json={"max_position_pct": 30, "motivo": "prueba"})
    r = isolated.delete("/api/limits/pendientes")
    assert r.status_code == 200
    assert isolated.get("/api/settings").json()["pendientes"] is None
    assert isolated.get("/api/settings").json()["limits"]["max_position_pct"] == 20
    assert any("cancelado" in _tesis(e) for e in _journal(isolated))
    assert isolated.delete("/api/limits/pendientes").status_code == 404


def test_validacion_de_entradas(isolated):
    assert isolated.put("/api/limits", json={"clave_rara": 5}).status_code == 400
    assert isolated.put("/api/limits", json={"max_position_pct": -1}).status_code == 400
    assert isolated.put("/api/limits", json={"max_position_pct": 101}).status_code == 400
    assert isolated.put("/api/limits", json={"max_position_pct": "30"}).status_code == 400
    assert isolated.put("/api/limits", json={"max_position_pct": True}).status_code == 400


def test_positions_target_es_preferencia_inmediata(isolated):
    r = isolated.put("/api/limits", json={"positions_target": 8})
    assert r.status_code == 200 and r.json()["pendientes"] is None
    assert r.json()["limits"]["positions_target"] == 8


# ---------- perfil ----------


def test_perfil_primer_valor_aplica_al_instante(isolated):
    r = isolated.put("/api/profile", json={"nivel_riesgo": "conservador",
                                           "perdida_maxima_pct": 10,
                                           "horizonte_anios": 5,
                                           "objetivo": "comprar casa"})
    assert r.status_code == 200
    assert r.json()["pendientes"] is None
    assert r.json()["profile"]["nivel_riesgo"] == "conservador"


def test_perfil_aflojar_queda_pendiente(isolated):
    isolated.put("/api/profile", json={"perdida_maxima_pct": 10})
    r = isolated.put("/api/profile", json={"perdida_maxima_pct": 25})
    assert r.status_code == 400                                    # falta motivo
    r = isolated.put("/api/profile", json={"perdida_maxima_pct": 25,
                                           "motivo": "aguanto más caída"})
    assert r.status_code == 200
    assert r.json()["pendientes"]["cambios"] == {"perdida_maxima_pct": 25}
    assert r.json()["profile"]["perdida_maxima_pct"] == 10
    assert isolated.get("/api/profile").json()["pendientes"]["cambios"]["perdida_maxima_pct"] == 25


def test_perfil_endurecer_aplica(isolated):
    isolated.put("/api/profile", json={"nivel_riesgo": "agresivo"})
    r = isolated.put("/api/profile", json={"nivel_riesgo": "moderado"})
    assert r.status_code == 200 and r.json()["pendientes"] is None
    assert r.json()["profile"]["nivel_riesgo"] == "moderado"


def test_perfil_cancelar(isolated):
    isolated.put("/api/profile", json={"perdida_maxima_pct": 10})
    isolated.put("/api/profile", json={"perdida_maxima_pct": 25, "motivo": "prueba"})
    assert isolated.delete("/api/profile/pendientes").status_code == 200
    assert isolated.get("/api/profile").json()["pendientes"] is None
    assert isolated.delete("/api/profile/pendientes").status_code == 404


def test_perfil_validacion(isolated):
    assert isolated.put("/api/profile", json={"campo_raro": 1}).status_code == 400
    assert isolated.put("/api/profile", json={"nivel_riesgo": "kamikaze"}).status_code == 400
    assert isolated.put("/api/profile", json={"perdida_maxima_pct": 150}).status_code == 400
