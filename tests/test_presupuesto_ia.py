"""Tope mensual duro del proveedor de IA: cuenta cada intento antes de la
red y se reinicia el día 1 del mes siguiente. Marcado presupuesto_ia para que
conftest no parchee consumir_presupuesto."""
from datetime import datetime, timezone

import pytest

from app import ai_provider as AIP
from app import db as D

ENV = {"INVERSOR_AI_API_KEY": "clave-de-prueba", "INVERSOR_AI_MODEL": "modelo-prueba",
       "INVERSOR_AI_BASE_URL": "https://ejemplo.test/v1", "INVERSOR_AI_API_STYLE": "chat"}


@pytest.fixture
def db_ia(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "ia.db"))
    D.init_db()


def _set(key, value):
    conn = D.get_db()
    D.set_setting(conn, D.local_user_id(conn), key, value)
    conn.commit()
    conn.close()


@pytest.mark.presupuesto_ia
def test_tope_bloquea_la_llamada_que_pasa(db_ia, fake_client):
    _set("ia_tope_mensual", 2)
    fake = fake_client({"choices": [{"message": {"content": "ok"}}]})
    AIP.request("i", "u", env=ENV, client=fake)
    AIP.request("i", "u", env=ENV, client=fake)
    assert len(fake.calls) == 2
    with pytest.raises(AIP.AIProviderError, match="Tope mensual de IA alcanzado"):
        AIP.request("i", "u", env=ENV, client=fake)
    assert len(fake.calls) == 2           # la red nunca se tocó en la tercera


@pytest.mark.presupuesto_ia
def test_el_mes_nuevo_reinicia_el_contador(db_ia):
    mes, otro_mes = (datetime(2026, 10, 5, tzinfo=timezone.utc),
                     datetime(2026, 11, 1, tzinfo=timezone.utc))
    _set("ia_tope_mensual", 1)
    AIP.consumir_presupuesto(now=mes)
    with pytest.raises(AIP.AIProviderError, match="Tope mensual"):
        AIP.consumir_presupuesto(now=mes)
    AIP.consumir_presupuesto(now=otro_mes)        # noviembre: cupo nuevo


@pytest.mark.presupuesto_ia
def test_config_status_expone_uso_mes(db_ia):
    AIP.consumir_presupuesto()
    uso = AIP.config_status()["uso_mes"]
    assert uso["mes"] == datetime.now(timezone.utc).strftime("%Y-%m")
    assert uso["llamadas"] == 1
    assert uso["tope"] == AIP.IA_TOPE_MENSUAL_DEFAULT
