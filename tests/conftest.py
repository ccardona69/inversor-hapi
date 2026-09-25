"""Configuración común de las pruebas.

La app inicializa SQLite al importarse: nunca usar inversor.db en las pruebas.
Todas las pruebas comparten esta BD temporal; la app es de un solo usuario
(sin login), así que las pruebas que requieren aislamiento total montan su
propia BD con tmp_path.
"""
import os
import tempfile

import pytest

os.environ["INVERSOR_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from app import marketdata as MD  # noqa: E402  (tras fijar INVERSOR_DB)
from app import marketpulse as MP  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "red: la prueba puede tocar Yahoo (integración tolerante a fallos)")


@pytest.fixture(autouse=True)
def sin_red(request, monkeypatch):
    """Ninguna prueba toca Yahoo salvo las marcadas con @pytest.mark.red: la descarga
    cruda falla como si no hubiera red (las que necesitan datos parchean
    fetch_quote/fetch_history). Las cachés del pulso y de niveles se limpian para
    que una prueba no contamine a otra."""
    def _sin_red(url):
        raise MD.MarketDataError("Fuente de datos no disponible (sin red en pruebas). "
                                 "Puedes ingresar el precio manualmente.")
    if request.node.get_closest_marker("red") is None:
        monkeypatch.setattr(MD, "_fetch_json", _sin_red)
    MP._clear_cache()
    yield
    MP._clear_cache()


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
