"""Inversor Hapi IA — API principal (FastAPI).

Sistema de apoyo a decisiones de inversión: transforma datos con fuente y fecha
en decisiones explicables. No promete rentabilidad, no inventa cifras, no
ejecuta operaciones: siempre propone, muestra riesgos y pide que el usuario
ejecute personalmente en su bróker.

Los endpoints viven en app/routes/, agrupados por dominio; este módulo arma la
aplicación y sirve el frontend.
"""
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import db as D
from .routes import ai, auth, decisions, market, portfolio, system, trades

app = FastAPI(title="Inversor Hapi IA", version="0.1.0")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
D.init_db()

for module in (auth, portfolio, market, trades, ai, decisions, system):
    app.include_router(module.router)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                        headers={"Cache-Control": "no-cache"})


# no-cache en todos los archivos del frontend: cambian junto con el código y sin
# esta cabecera el navegador mostraba versiones viejas con funciones ausentes.
@app.get("/app.css")
def app_css():
    return FileResponse(os.path.join(STATIC_DIR, "app.css"),
                        headers={"Cache-Control": "no-cache"})


@app.get("/app.js")
def app_js():
    return FileResponse(os.path.join(STATIC_DIR, "app.js"),
                        headers={"Cache-Control": "no-cache"})
