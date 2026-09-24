# CLAUDE.md — guía del proyecto para agentes

## Qué es
Apoyo a decisiones de inversión para usuarios de Hapi. Toma datos con fuente y fecha y propone decisiones explicables (comprar/mantener/reducir/etc.). **Nunca ejecuta operaciones** ni inventa cifras: propone y registra, el usuario opera en su bróker.

## Stack
FastAPI + SQLite (WAL). Frontend: SPA sin dependencias (`static/index.html` + `static/app.css` + `static/app.js`). Python.

## Cómo levantarlo
```bash
cd inversor-hapi
pip install -r requirements.txt          # fastapi uvicorn pytest httpx
python run_local.py                      # elige puerto libre y abre el navegador
# alternativas: iniciar-local.cmd (Windows, doble clic), --no-browser, --port NNNN
# abrir http://127.0.0.1:<puerto>
```

## Cómo probar
```bash
python -m pytest tests/ -q               # 163 pruebas en 8 archivos
```
No piden red (precios manuales); el fetch real de Yahoo se prueba aparte y de forma tolerante a fallos. La BD de pruebas la fija `tests/conftest.py` (nunca `inversor.db`). Regla de la casa: no digas "funciona" sin correr esto y mostrar la salida.

## Arquitectura
- `app/main.py` — arma la FastAPI (`include_router`) y sirve el frontend.
- `app/routes/` — endpoints por dominio: `auth.py` (sesión y perfil), `portfolio.py` (cartera, efectivo, importación y foto de Hapi, validación), `market.py` (precios y fundamentales manuales o por foto), `trades.py` (libro de órdenes y reconciliación de costo), `ai.py` (consultas a Luna), `decisions.py` (análisis, decisiones, riesgo, simulador, candidatos, alertas, diario, panel), `system.py` (límites, auditoría, borrado).
- `app/deps.py` — dependencias compartidas (`conn_dep`, `current_user`, `_photo_input`, `DISCLAIMER`).
- `app/ai_provider.py` — capa única del proveedor de IA: configuración (`.secrets/ai.env` o env `INVERSOR_AI_*`), endpoint, armado del cuerpo y extracción de respuesta. Ningún otro módulo habla con el proveedor.
- `app/photosync.py` / `fundsync.py` / `tradesync.py` — extracción por foto (cartera / fundamentales / órdenes) con prompts propios y validación estricta.
- `app/ai_assistant.py` / `ai_review.py` — consultas a Luna y revisión de tesis / explicación de decisiones.
- `app/marketdata.py` — precios de Yahoo Finance (sin clave) + indicadores.
- `app/analysis.py` — scores fundamentales, múltiplos, DCF por escenarios.
- `app/risk.py` — concentración, correlación, límites, estrés.
- `app/decisions.py` — motor de decisiones y checklist de "promediar a la baja".
- `app/db.py` — esquema SQLite (13 tablas) y utilidades de datos.
- `run_local.py` + `iniciar-local.cmd` — lanzador local (puerto libre + navegador).

## Qué NO tocar
- `inversor.db` y `.secrets/` — datos y credenciales fuera de Git (en `.gitignore`). No los subas.
- El principio del producto: nunca inventar cifras, todo dato lleva fuente y fecha, nunca ejecutar órdenes. Si un cambio rompe eso, avisa antes.

## Notas
- Variable de entorno opcional: `INVERSOR_DB` (ruta de la base de datos).
- La API de Yahoo puede cambiar sin aviso; por eso existe el ingreso manual de precios.
- Los endpoints se sirven con `Cache-Control: no-cache` para que el navegador nunca muestre un frontend viejo.
