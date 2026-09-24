"""Configuración común de las pruebas.

La app inicializa SQLite al importarse: nunca usar inversor.db en las pruebas.
Todas las pruebas comparten esta BD temporal; el aislamiento entre módulos lo
dan los usuarios distintos que cada uno registra (la API filtra todo por user_id)
y las pruebas que requieren aislamiento total montan su propia BD con tmp_path.
"""
import os
import tempfile

import pytest

os.environ["INVERSOR_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")


class FakeClient:
    """Cliente httpx falso para el proveedor de IA: registra las llamadas como
    tuplas (url, headers, body) y devuelve siempre `payload` con `status`."""

    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status
        self.calls = []

    def post(self, url, headers=None, json=None):
        self.calls.append((url, headers, json))
        return self

    @property
    def status_code(self):
        return self.status

    def json(self):
        return self.payload


@pytest.fixture
def fake_client():
    return FakeClient
