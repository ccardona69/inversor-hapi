# inversor-hapi

## Qué es
Apoyo a decisiones de inversión para usuarios de Hapi. Toma datos con fuente y fecha y propone decisiones explicables (comprar/mantener/reducir/etc.). **Nunca ejecuta operaciones** ni inventa cifras: propone y registra, el usuario opera en su bróker.

## Stack
FastAPI + SQLite. Frontend: una sola página sin dependencias (`static/index.html`). Python.

## Cómo levantarlo
```bash
cd inversor-hapi
pip install -r requirements.txt          # fastapi uvicorn pytest httpx
uvicorn app.main:app --reload --port 8100
# abrir http://localhost:8100
```

## Cómo probar
```bash
python -m pytest tests/ -q               # 21 pruebas, no dependen de la red
```
Regla de la casa: no digas "funciona" sin correr esto y mostrar la salida.

## Archivos clave
- `app/main.py` — la API y el formato de recomendación
- `app/marketdata.py` — precios de Yahoo Finance (sin clave) + indicadores
- `app/analysis.py` — scores fundamentales, múltiplos, DCF por escenarios
- `app/risk.py` — concentración, correlación, límites, estrés
- `app/decisions.py` — motor de decisiones y checklist de "promediar a la baja"
- `app/db.py` — esquema SQLite
- `app/photosync.py` — sincronización de cartera por foto (IA de visión)

## Sincronización por foto (IA)
El usuario sube una captura de su cartera en Hapi; un modelo de visión extrae las
posiciones y el efectivo, el usuario los revisa/edita en una tabla y confirma. Nada
se guarda sin confirmación y todo entra «pendiente de verificación» con la fuente visible.

- Credenciales en `.secrets/ai.env` (fuera de Git) o variables de entorno:
  `INVERSOR_AI_API_KEY`, `INVERSOR_AI_BASE_URL`, `INVERSOR_AI_MODEL`,
  `INVERSOR_AI_API_STYLE` (`responses` para Azure Foundry/GPT-5.x, `chat` para el resto).
- Endpoints: `GET /api/hapi/photo/status`, `POST /api/hapi/photo/analyze`, `POST /api/hapi/photo/save`.
- Regla crítica: la IA nunca inventa cifras; lo que no se ve en la captura llega `null`.

## Qué NO tocar
- `inversor.db` — base de datos, está fuera de Git (en `.gitignore`). No la subas.
- El principio del producto: nunca inventar cifras, todo dato lleva fuente y fecha, nunca ejecutar órdenes. Si un cambio rompe eso, avisá antes.

## Notas
- Variable de entorno opcional: `INVERSOR_DB` (ruta de la base de datos).
- La API de Yahoo puede cambiar sin aviso; por eso existe el ingreso manual de precios.
