"""Inicia la app solo en esta computadora y abre la instancia que acaba de arrancar."""
import argparse
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

HOST = "127.0.0.1"


def open_when_ready(url, stop, open_browser):
    deadline = time.monotonic() + 20
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200 and not stop.is_set():
                    print(f"\nAbre tu cartera: {url}", flush=True)
                    if open_browser:
                        webbrowser.open(url)
                    return
        except (OSError, urllib.error.URLError):
            pass
        stop.wait(0.2)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Abre Inversor Hapi IA solo en esta computadora")
    parser.add_argument("--port", type=int, default=0,
                        help="puerto local; por defecto se elige uno libre para evitar servidores antiguos")
    parser.add_argument("--no-browser", action="store_true", help="muestra la dirección sin abrir el navegador")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("el puerto debe estar entre 0 y 65535")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind((HOST, args.port))
            listener.listen(socket.SOMAXCONN)
        except OSError as exc:
            parser.error(f"no se pudo reservar el puerto local: {exc}. Prueba sin --port")
        port = listener.getsockname()[1]
        url = f"http://{HOST}:{port}/"
        config = uvicorn.Config("app.main:app", host=HOST, port=port, reload=False, access_log=False)
        server = uvicorn.Server(config)
        stop = threading.Event()
        ready = threading.Thread(target=open_when_ready, args=(url, stop, not args.no_browser), daemon=True)
        ready.start()
        try:
            server.run(sockets=[listener])
        finally:
            stop.set()
            ready.join(timeout=2)
        if not server.started:
            raise SystemExit("No se pudo iniciar la aplicación. Revisa el error anterior.")


if __name__ == "__main__":
    main()
