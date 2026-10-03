"""Pruebas sin red del asistente de consulta a Luna."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_assistant as AI
from app import ai_provider as AP
from app import db as D
from app.main import app

# La suite previa prueba el interior de las funciones; la puerta del
# modo plan (409 con el ETF bajo la meta) se abre con el estado inactivo.
pytestmark = pytest.mark.usefixtures("sin_modo_plan")



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
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "assistant.db"))
    D.init_db()
    return TestClient(app)


def test_assistant_validation_and_readonly_context(session, monkeypatch):
    assert session.post("/api/assistant/ask", json={"question": "   "}).status_code == 400
    assert session.post("/api/assistant/ask", json={"question": "x" * 601}).status_code == 422
    assert session.post("/api/positions", json={"ticker": "NVDA", "qty": 2,
        "invested": 100, "source": "captura propia 2026-09-01"}).status_code == 200
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    assert session.post("/api/prices/manual", json={"ticker": "NVDA", "price": 50,
        "source": "precio manual", "asof": old}).status_code == 200
    assert session.put("/api/fundamentals/NVDA", json={"data": {"eps": 2.5},
        "source": "informe de prueba", "asof": "2026-06-01"}).status_code == 200
    assert session.post("/api/journal", json={"ticker": "NVDA", "action": "revision",
        "tesis": "Tesis privada", "riesgos": "riesgo de prueba"}).status_code == 200

    captured = []
    def fake_ask(question, context, history=None):
        captured.append((question, context, history))
        return {"answer": "Verifica los datos", "model": "modelo-de-prueba", "asof": context["fecha_consulta"]}
    monkeypatch.setattr(AI, "ask", fake_ask)
    before = session.get("/api/portfolio").json()
    r = session.post("/api/assistant/ask", json={"question": "  ¿Qué debo verificar?  "})
    assert r.status_code == 200 and r.json()["answer"] == "Verifica los datos"
    assert session.get("/api/portfolio").json() == before
    question, context, _history = captured[-1]
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
    assert session.get("/api/assistant/status").status_code == 200


@pytest.mark.parametrize("style", ["responses", "chat"])
def test_ask_sends_history_before_the_current_question(fake_client, style):
    cfg = dict(CONFIG, INVERSOR_AI_API_STYLE=style,
               INVERSOR_AI_BASE_URL="https://recurso.services.ai.azure.com/foundry/openai/v1"
               if style == "responses" else "https://recurso.openai.azure.com")
    payload = ({"output": [{"content": [{"type": "output_text", "text": "vale"}]}]}
               if style == "responses" else {"choices": [{"message": {"content": "vale"}}]})
    fake = fake_client(payload)
    history = [{"role": "user", "content": "primera"}, {"role": "assistant", "content": "respuesta"}]
    AI.ask("segunda", {"fecha_consulta": "hoy"}, env=cfg, client=fake, history=history)
    body = fake.calls[0][2]
    if style == "responses":
        assert body["input"][:2] == history
        assert body["input"][2]["role"] == "user"
        assert body["input"][2]["content"][0]["type"] == "input_text"
        assert "segunda" in body["input"][2]["content"][0]["text"]
    else:
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1:3] == history
        assert body["messages"][3]["role"] == "user" and "segunda" in body["messages"][3]["content"]


def test_ask_without_history_keeps_the_original_body(fake_client):
    fake = fake_client({"output": [{"content": [{"type": "output_text", "text": "vale"}]}]})
    AI.ask("hola", {"fecha_consulta": "hoy"}, env=CONFIG, client=fake)
    body = fake.calls[0][2]
    assert len(body["input"]) == 1 and body["input"][0]["role"] == "user"


def test_assistant_provider_failure_does_not_change_positions(session, monkeypatch):
    before = session.get("/api/portfolio").json()
    def fail(*args, **kwargs):
        raise AI.AssistantError("Servicio no disponible")
    monkeypatch.setattr(AI, "ask", fail)
    response = session.post("/api/assistant/ask", json={"question": "¿Y mi cartera?"})
    assert response.status_code == 502 and response.json()["detail"] == "Servicio no disponible"
    assert session.get("/api/portfolio").json() == before


def test_assistant_history_validation_and_relay(session, monkeypatch):
    too_long = [{"role": "user", "content": "x"}] * 9
    assert session.post("/api/assistant/ask",
                        json={"question": "hola", "history": too_long}).status_code == 422
    bad_role = [{"role": "system", "content": "x"}]
    assert session.post("/api/assistant/ask",
                        json={"question": "hola", "history": bad_role}).status_code == 422
    captured = {}
    def fake_ask(question, context, history=None):
        captured["history"] = history
        return {"answer": "ok", "model": "modelo-de-prueba", "asof": context["fecha_consulta"]}
    monkeypatch.setattr(AI, "ask", fake_ask)
    history = [{"role": "user", "content": "antes"}, {"role": "assistant", "content": "previa"}]
    r = session.post("/api/assistant/ask", json={"question": "ahora", "history": history})
    assert r.status_code == 200 and captured["history"] == history


def test_context_includes_alerts_limits_and_latest_proposals(session, monkeypatch):
    session.post("/api/positions", json={"ticker": "NVDA", "qty": 2, "invested": 200})
    session.post("/api/prices/manual", json={"ticker": "NVDA", "price": 120, "source": "prueba",
                                             "asof": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    conn = D.get_db()
    uid = D.local_user_id(conn)
    for prop in ('{"decision":"mantener","confianza":"media"}', '{"decision":"reducir","confianza":"baja"}'):
        conn.execute("INSERT INTO decisions (user_id, ticker, proposal, created_at) VALUES (?,?,?,?)",
                     (uid, "NVDA", prop, D.now()))
    conn.commit()
    conn.close()
    captured = {}
    def fake_ask(question, context, history=None):
        captured["context"] = context
        return {"answer": "ok", "model": "modelo-de-prueba", "asof": context["fecha_consulta"]}
    monkeypatch.setattr(AI, "ask", fake_ask)
    r = session.post("/api/assistant/ask", json={"question": "¿Cómo voy?"})
    assert r.status_code == 200
    context = captured["context"]
    position = context["posiciones"][0]
    assert position["valor_mercado"] == 240 and position["peso_pct"] == 100.0
    assert position["resultado"] == 40 and position["rendimiento_pct"] == 20.0
    assert position["cambio_dia_pct"] is None  # el precio manual no trae cambio diario
    assert context["alertas"] and set(context["alertas"][0]) == {"nivel", "texto"}
    assert context["limites"]["max_position_pct"] == 25.0
    prop = context["ultimas_propuestas"][0]
    assert prop["ticker"] == "NVDA" and prop["propuesta"] == "reducir" and prop["confianza"] == "baja"
    assert len(context["ultimas_propuestas"]) == 1  # una propuesta por ticker
    assert "password" not in str(context) and "email" not in str(context)
