"""Entrada de flujos por texto, historial y captura: pruebas puras + IA falsa."""
import json

import pytest

from app import ai_provider as AP
from app import flowsync as FS

ENV_CHAT = {"INVERSOR_AI_API_KEY": "clave-de-prueba", "INVERSOR_AI_MODEL": "luna-prueba",
            "INVERSOR_AI_BASE_URL": "https://recurso.openai.azure.com",
            "INVERSOR_AI_API_STYLE": "chat"}

TODAY = "2026-09-26"


def test_parse_ahorro():
    for text in ("guardé 80 soles", "ahorré 80 soles", "guarde S/ 80", "Guardé 80"):
        rows = FS.parse_message(text, TODAY)
        assert rows == [{"kind": "ahorro_soles", "soles_amount": 80,
                         "at": TODAY, "source": "texto"}], text


def test_parse_deposito_con_llegada():
    for text in ("deposité 480 soles y llegaron 132.50",
                 "deposité S/480 y llegaron $132.50"):
        rows = FS.parse_message(text, TODAY)
        assert len(rows) == 1, text
        r = rows[0]
        assert r["kind"] == "deposito" and r["at"] == TODAY and r["source"] == "texto"
        assert r["soles_amount"] == 480 and r["amount_usd"] == 132.5
        assert r["fx_rate"] == round(480 / 132.5, 4)


def test_parse_deposito_sin_llegada():
    r = FS.parse_message("deposité 480 soles", TODAY)[0]
    assert r["kind"] == "deposito" and r["soles_amount"] == 480
    assert "amount_usd" not in r and "fx_rate" not in r


def test_parse_actividad_y_w8ben():
    rows = FS.parse_message("entré a Hapi", TODAY)
    assert rows == [{"kind": "actividad", "at": TODAY}]
    for text, exp in (("mi W-8BEN vence el 2027-03-01", "2027-03-01"),
                      ("mi W-8BEN vence el 01/03/2027", "2027-03-01")):
        rows = FS.parse_message(text, TODAY)
        assert rows == [{"kind": "w8ben", "at": exp}], text


def test_parse_fecha_explicita():
    rows = FS.parse_message("guardé 80 soles el 26/12/2025", TODAY)
    assert rows[0]["at"] == "2025-12-26"
    rows = FS.parse_message("guardé 80 soles el 2025-12-26", TODAY)
    assert rows[0]["at"] == "2025-12-26"


def test_parse_no_entendido_devuelve_vacio():
    assert FS.parse_message("hola", TODAY) == []
    assert FS.parse_message("", TODAY) == []


def test_fingerprint_coalesce_y_canonico():
    a80 = {"kind": "ahorro_soles", "soles_amount": 80, "at": "2026-09-26"}
    a120 = {"kind": "ahorro_soles", "soles_amount": 120, "at": "2026-09-26"}
    assert FS.fingerprint(a80) != FS.fingerprint(a120)
    dep_txt = {"kind": "deposito", "amount_usd": 221.5, "at": "2026-08-25"}
    dep_cap = {"kind": "deposito", "amount_usd": 221.50, "at": "2026-08-25",
               "source": "captura"}
    assert FS.fingerprint(dep_txt) == FS.fingerprint(dep_cap)


def test_normalize_movement_valida_campos():
    ok = FS.normalize_movement({"kind": "deposito", "amount_usd": 9,
                                "at": "2025-12-26"})
    assert ok == {"kind": "deposito", "amount_usd": 9, "at": "2025-12-26"}
    for raw in ({"kind": "compra", "amount_usd": 9, "at": "2025-12-26"},
                {"kind": "deposito", "amount_usd": 0, "at": "2025-12-26"},
                {"kind": "deposito", "amount_usd": -5, "at": "2025-12-26"},
                {"kind": "deposito", "amount_usd": None, "at": "2025-12-26"},
                {"kind": "deposito", "amount_usd": 9, "at": "ayer"},
                {"kind": "deposito", "amount_usd": 9, "at": None},
                "no es fila"):
        with pytest.raises(FS.FlowSyncError):
            FS.normalize_movement(raw)


def test_analyze_text_solo_terminado(fake_client):
    """El historial real trae un $80 «Creado» y un $20 «Expirado»: no entran."""
    reply = {"rows": [
        {"kind": "deposito", "amount_usd": 9, "at": "2025-12-26", "status": "Terminado"},
        {"kind": "deposito", "amount_usd": 20, "at": "2026-02-06", "status": "Expirado"},
        {"kind": "deposito", "amount_usd": 80, "at": "2026-04-08", "status": "Creado"},
        {"kind": "dividendo", "amount_usd": 0.42, "at": "2026-06-01", "status": "Terminado"},
        {"kind": "deposito", "amount_usd": 5, "at": "2026-01-05", "status": "Cancelado"},
    ], "omitted": [{"motivo": "compra de acciones, no es flujo"}]}
    fake = fake_client({"choices": [{"message": {"content": json.dumps(reply)}}]})
    out = FS.analyze_text("historial de movimientos pegado de Hapi",
                          env=ENV_CHAT, client=fake)
    assert out["model"] == "luna-prueba"
    assert [(r["amount_usd"], r["kind"]) for r in out["rows"]] == [
        (9, "deposito"), (0.42, "dividendo")]
    assert all(r["source"] == "historial" for r in out["rows"])
    assert len(out["omitted"]) == 4  # 1 previa + Creado + Expirado + Cancelado
    assert all("Terminado" in json.dumps(o, ensure_ascii=False) or "motivo" in o
               for o in out["omitted"])


def test_analyze_text_errores_proveedor_y_respuesta(fake_client, tmp_path, monkeypatch):
    monkeypatch.setattr(AP, "SECRETS_FILE", tmp_path / "ausente.env")
    fake = fake_client({"choices": [{"message": {"content": "no soy json"}}]})
    with pytest.raises(FS.FlowSyncError):
        FS.analyze_text("texto de historial suficientemente largo", env=ENV_CHAT, client=fake)
    with pytest.raises(FS.FlowSyncError, match="configurada"):
        FS.analyze_text("texto de historial suficientemente largo", env={}, client=fake)
    with pytest.raises(FS.FlowSyncError):
        FS.analyze_text("", env=ENV_CHAT, client=fake)


def test_analyze_image_marca_fuente_captura(monkeypatch):
    def fake_request(instructions, user_text, **kwargs):
        return {"rows": [{"kind": "deposito", "amount_usd": 65,
                          "at": "2026-09-08", "status": "Terminado"}],
                "omitted": []}, "vision-prueba"
    monkeypatch.setattr(AP, "request", fake_request)
    out = FS.analyze_image("aW1hZ2Vu", "image/png")
    assert out["rows"][0]["source"] == "captura" and out["model"] == "vision-prueba"


def test_normalize_row_confirmacion():
    row = FS.normalize_row({"kind": "deposito", "soles_amount": 480,
                            "amount_usd": 132.5, "fx_rate": 3.6226,
                            "at": "2026-09-08", "source": "texto"})
    assert row["fingerprint"] and row["source"] == "texto"
    assert FS.normalize_row({"kind": "actividad", "at": "2026-09-08"}) == {
        "kind": "actividad", "at": "2026-09-08"}
    for raw in ({"kind": "luna", "at": "2026-09-08"},
                {"kind": "deposito", "at": "2026-09-08"},        # sin montos
                {"kind": "ahorro_soles", "at": "2026-09-08"},    # sin soles
                {"kind": "retiro", "soles_amount": 50, "at": "2026-09-08"},
                {"kind": "deposito", "amount_usd": 9, "at": "2026-09-08",
                 "source": "inventada"}):
        with pytest.raises(FS.FlowSyncError):
            FS.normalize_row(raw)
