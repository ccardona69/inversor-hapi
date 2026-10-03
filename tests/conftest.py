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

from app import ai_provider as AIP  # noqa: E402
from app import marketdata as MD  # noqa: E402  (tras fijar INVERSOR_DB)
from app import marketpulse as MP  # noqa: E402
from app import secdata as SD  # noqa: E402
from app.routes import marcador as MARC  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "red: la prueba puede tocar Yahoo (integración tolerante a fallos)")
    config.addinivalue_line("markers", "presupuesto_ia: la prueba usa el tope mensual real de IA (sin parchear consumir_presupuesto)")


@pytest.fixture(autouse=True)
def sin_red(request, monkeypatch):
    """Ninguna prueba toca la red salvo las marcadas con @pytest.mark.red: la descarga
    cruda de Yahoo falla como si no hubiera red (las que necesitan datos parchean
    fetch_quote/fetch_history). SEC y el proveedor de IA solo funcionan con un
    cliente inyectado: sin cliente, la llamada falla. Las cachés del pulso y de
    niveles se limpian para que una prueba no contamine a otra."""
    if request.node.get_closest_marker("red") is None:
        def _sin_red(url):
            raise MD.MarketDataError("Fuente de datos no disponible (sin red en pruebas). "
                                     "Puedes ingresar el precio manualmente.")
        monkeypatch.setattr(MD, "_fetch_json", _sin_red)

        sec_get = SD._get

        def _sec_sin_red(url, client=None):
            if client is None:
                raise SD.SecDataError(502, "SEC bloqueada: sin red en pruebas.")
            return sec_get(url, client)

        monkeypatch.setattr(SD, "_get", _sec_sin_red)

        ai_request = AIP.request

        def _ai_sin_red(*args, client=None, **kwargs):
            if client is None:
                raise AIP.AIProviderError("Proveedor de IA bloqueado: sin red en pruebas.")
            return ai_request(*args, client=client, **kwargs)

        monkeypatch.setattr(AIP, "request", _ai_sin_red)
    if request.node.get_closest_marker("presupuesto_ia") is None:
        # El tope mensual real solo corre en las pruebas del marcador
        # presupuesto_ia; al resto no le descuenta llamadas.
        monkeypatch.setattr(AIP, "consumir_presupuesto", lambda now=None: None)
    MP._clear_cache()
    MARC._clear_cache()
    yield
    MP._clear_cache()
    MARC._clear_cache()


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


@pytest.fixture
def sin_modo_plan(monkeypatch):
    """Abre la puerta del modo plan para la suite previa: las pruebas de radar,
    pulso, Luna, análisis y trade_check siguen probando su interior con un
    estado de plan inactivo. La puerta en sí se prueba en test_modo_plan.py."""
    monkeypatch.setattr(MARC, "modo_plan_estado",
                        lambda conn, uid: {"activo": False, "etf_pct": None,
                                           "meta_pct": None, "motivo": None})
