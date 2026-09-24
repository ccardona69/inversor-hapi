"""Pruebas sin red del asistente de consulta a Luna."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_assistant as AI
from app import ai_provider as AP
from app import db as D
from app.main import app


CONFIG = {"INVERSOR_AI_API_KEY": "clave-de-prueba", "INVERSOR_AI_MODEL": "gpt-5.6-luna",
          "INVERSOR_AI_BASE_URL": "https://recurso.services.ai.azure.com/foundry/openai/v1",
          "INVERSOR_AI_API_STYLE": "responses"}


def test_ask_uses_same_responses_provider_without_image(fake_client):
    fake = fake_client({"output": [{"content": [{"type": "output_text", "text": "Sin datos suficientes."}]}]})
    result = AI.ask("¿Tengo riesgo?", {"fecha_consulta": "2026-09-23", "posiciones": []},
                    env=CONFIG, client=fake)
    assert result == {"answer": "Sin datos suficientes.", "model": "gpt-5.6-luna", "asof": "2026-09-23"}
    url, headers, body = fake.calls[0]
    assert url.endswith("/foundry/openai/v1/responses")
    assert headers["api-key"] == "clave-de-prueba"
    assert body["input"][0]["content"][0]["type"] == "input_text"
    assert "¿Tengo riesgo?" in body["input"][0]["content"][0]["text"]
    assert "input_image" not in str(body)
    assert "Nunca inventes precios" in body["instructions"]


def test_ask_chat_and_error_paths(tmp_path, monkeypatch, fake_client):
    monkeypatch.setattr(AP, "SECRETS_FILE", tmp_path / "ausente.env")
    cfg = dict(CONFIG, INVERSOR_AI_API_STYLE="chat", INVERSOR_AI_BASE_URL="https://recurso.openai.azure.com")
    fake = fake_client({"choices": [{"message": {"content": "  Revisa la fecha. "}}]})
    assert AI.ask("¿Es actual?", {"fecha_consulta": "hoy"}, env=cfg, client=fake)["answer"] == "Revisa la fecha."
    assert "/chat/completions" in fake.calls[0][0]
    assert fake.calls[0][2]["messages"][0]["role"] == "system"
    with pytest.raises(AI.AssistantError, match="no configurada"):
        AI.ask("hola", {}, env={}, client=fake)
    with pytest.raises(AI.AssistantError, match="rechazó"):
        AI.ask("hola", {}, env=CONFIG, client=fake_client({}, status=401))
    with pytest.raises(AI.AssistantError, match="interpretable"):
        AI.ask("hola", {}, env=CONFIG, client=fake_client({"output": []}))


@pytest.fixture
def users(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "assistant.db"))
    D.init_db()
    first, second = TestClient(app), TestClient(app)
    assert first.post("/api/register", json={"email": "primero@test.pe", "password": "clave-segura-1"}).status_code == 200
    assert second.post("/api/register", json={"email": "segundo@test.pe", "password": "clave-segura-2"}).status_code == 200
    return first, second


def test_assistant_auth_validation_and_isolation(users, monkeypatch):
    first, second = users
    assert TestClient(app).post("/api/assistant/ask", json={"question": "hola"}).status_code == 401
    assert first.post("/api/assistant/ask", json={"question": "   "}).status_code == 400
    assert first.post("/api/assistant/ask", json={"question": "x" * 601}).status_code == 422
    assert first.post("/api/positions", json={"ticker": "NVDA", "qty": 2,
        "invested": 100, "source": "captura propia 2026-09-01"}).status_code == 200
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    assert first.post("/api/prices/manual", json={"ticker": "NVDA", "price": 50,
        "source": "precio manual", "asof": old}).status_code == 200
    assert first.put("/api/fundamentals/NVDA", json={"data": {"eps": 2.5},
        "source": "informe de prueba", "asof": "2026-06-01"}).status_code == 200
    assert first.post("/api/journal", json={"ticker": "NVDA", "action": "revision",
        "tesis": "Tesis privada", "riesgos": "riesgo de prueba"}).status_code == 200

    captured = []
    def fake_ask(question, context):
        captured.append((question, context))
        return {"answer": "Verifica los datos", "model": "modelo-de-prueba", "asof": context["fecha_consulta"]}
    monkeypatch.setattr(AI, "ask", fake_ask)
    before = first.get("/api/portfolio").json()
    r = first.post("/api/assistant/ask", json={"question": "  ¿Qué debo verificar?  "})
    assert r.status_code == 200 and r.json()["answer"] == "Verifica los datos"
    assert first.get("/api/portfolio").json() == before
    question, context = captured[-1]
    assert question == "¿Qué debo verificar?"
    position = context["posiciones"][0]
    assert position["ticker"] == "NVDA" and position["verificada"] is False
    assert position["fuente_posicion"] == "captura propia 2026-09-01"
    assert position["precio"] == {"valor": 50, "moneda": "USD", "fuente": "precio manual",
                                  "fecha": old, "estado": "desactualizado"}
    assert context["fundamentales"][0]["fuente"] == "informe de prueba"
    assert context["fundamentales"][0]["fecha"] == "2026-06-01"
    assert context["tesis_recientes"][0]["tesis"] == "Tesis privada"
    assert context["riesgo_calculado"]["sin_precio_vigente"] == ["NVDA"]
    assert "no calculable" in context["riesgo_calculado"]["error"]
    assert "password" not in str(context) and "email" not in str(context)

    assert second.post("/api/assistant/ask", json={"question": "¿Qué tengo?"}).status_code == 200
    other = captured[-1][1]
    assert other["posiciones"] == [] and other["fundamentales"] == [] and other["tesis_recientes"] == []
    assert second.get("/api/assistant/status").status_code == 200


def test_assistant_provider_failure_does_not_change_positions(users, monkeypatch):
    first, _ = users
    before = first.get("/api/portfolio").json()
    def fail(*args):
        raise AI.AssistantError("Servicio no disponible")
    monkeypatch.setattr(AI, "ask", fail)
    response = first.post("/api/assistant/ask", json={"question": "¿Y mi cartera?"})
    assert response.status_code == 502 and response.json()["detail"] == "Servicio no disponible"
    assert first.get("/api/portfolio").json() == before
