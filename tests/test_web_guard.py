"""Candado web: sin login, solo Host declarado y Origin/Referer propio en mutaciones."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)  # TestClient usa Host "testserver", incluido por defecto


def test_host_permitido_responde():
    assert client.get("/").status_code == 200


def test_host_extrano_rechazado():
    r = client.get("/", headers={"host": "evil.example.com"})
    assert r.status_code == 403


def test_mutacion_con_origin_ajeno_rechazada():
    r = client.post("/api/assistant/ask", json={"question": "hola"},
                    headers={"origin": "https://evil.example.com"})
    assert r.status_code == 403


def test_mutacion_con_origin_propio_o_sin_origen_pasa():
    propio = client.post("/api/assistant/ask", json={"question": "hola"},
                         headers={"origin": "http://testserver"})
    sin_origin = client.post("/api/assistant/ask", json={"question": "hola"})
    assert propio.status_code != 403
    assert sin_origin.status_code != 403
