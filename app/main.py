"""Inversor Hapi IA — API principal (FastAPI).

Sistema de apoyo a decisiones de inversión: transforma datos con fuente y fecha
en decisiones explicables. No promete rentabilidad, no inventa cifras, no
ejecuta operaciones: siempre propone, muestra riesgos y pide que el usuario
ejecute personalmente en su bróker.

Los endpoints viven en app/routes/, agrupados por dominio; este módulo arma la
aplicación y sirve el frontend.
"""
import os
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from . import db as D
from .routes import ai, decisions, marcador, market, portfolio, profile, radar, system, trades

app = FastAPI(title="Inversor Hapi IA", version="0.1.0")

# Sin login, esta es la única barrera web: Host declarado en INVERSOR_ALLOWED_HOSTS
# y mutaciones solo con Origin/Referer propio (rebiding/CSRF desde otras webs).
_ALLOWED_HOSTS = frozenset(
    h.strip().lower()
    for h in os.environ.get(
        "INVERSOR_ALLOWED_HOSTS", "127.0.0.1,localhost,::1,testserver"
    ).split(",")
    if h.strip()
)


@app.middleware("http")
async def host_origin_guard(request, call_next):
    host = (urlparse("//" + (request.headers.get("host") or "")).hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        return JSONResponse({"detail": "host no permitido"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        source = request.headers.get("origin") or request.headers.get("referer") or ""
        if source and (urlparse(source).hostname or "").lower() not in _ALLOWED_HOSTS:
            return JSONResponse({"detail": "origen no permitido"}, status_code=403)
    return await call_next(request)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
D.init_db()
# Snapshot diario al arrancar: el ledger es irreemplazable, el código no.
# Además queda un export JSON append-only legible sin la app.
if D.backup_due():
    D.backup_db()
    _conn = D.get_db()
    try:
        D.export_snapshot(D.local_user_id(_conn))
    finally:
        _conn.close()

for module in (profile, portfolio, market, trades, ai, decisions, radar, system, marcador):
    app.include_router(module.router)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                        headers={"Cache-Control": "no-cache"})


@app.get("/app.css")
def app_css():
    return FileResponse(os.path.join(STATIC_DIR, "app.css"),
                        headers={"Cache-Control": "no-cache"})


@app.get("/app.js")
def app_js():
    return FileResponse(os.path.join(STATIC_DIR, "app.js"),
                        headers={"Cache-Control": "no-cache"})

