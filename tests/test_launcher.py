"""El iniciador reserva solo loopback y nunca reutiliza otra instancia."""
import socket
import threading

import pytest

import run_local


def test_launcher_reserves_free_loopback_port_and_closes_socket(monkeypatch):
    observed = {}

    class FakeServer:
        def __init__(self, config):
            observed["config"] = config
            self.started = True

        def run(self, sockets):
            observed["socket"] = sockets[0]
            assert sockets[0].getsockname()[0] == "127.0.0.1"
            assert sockets[0].getsockname()[1] == observed["config"].port

    monkeypatch.setattr(run_local.uvicorn, "Server", FakeServer)
    run_local.main(["--no-browser"])
    assert observed["config"].host == "127.0.0.1"
    assert observed["config"].reload is False
    assert observed["socket"].fileno() == -1


def test_launcher_refuses_occupied_port_without_killing_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as existing:
        existing.bind(("127.0.0.1", 0))
        existing.listen(1)
        port = existing.getsockname()[1]
        with pytest.raises(SystemExit) as error:
            run_local.main(["--port", str(port), "--no-browser"])
        assert error.value.code == 2
        assert existing.fileno() != -1


def test_launcher_does_not_open_browser_when_startup_fails(monkeypatch):
    class FailedServer:
        started = False
        def __init__(self, config):
            pass
        def run(self, sockets):
            pass

    monkeypatch.setattr(run_local.uvicorn, "Server", FailedServer)
    monkeypatch.setattr(run_local.webbrowser, "open", lambda url: pytest.fail("Navegador abierto antes de iniciar"))
    with pytest.raises(SystemExit, match="No se pudo iniciar"):
        run_local.main([])


def test_launcher_opens_browser_only_after_http_success(monkeypatch):
    opened = []

    class ReadyResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(run_local.urllib.request, "urlopen", lambda *args, **kwargs: ReadyResponse())
    monkeypatch.setattr(run_local.webbrowser, "open", opened.append)
    run_local.open_when_ready("http://127.0.0.1:9999/", threading.Event(), True)
    assert opened == ["http://127.0.0.1:9999/"]
