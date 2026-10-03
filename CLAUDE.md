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
python -m pytest tests/ -q               # suite sin red; la cifra varía al agregar pruebas
node --check static/app.js
node --test tests/frontend.test.js       # pruebas de presentación sin dependencias
```
No piden red: `tests/conftest.py` bloquea `marketdata._fetch_json` en todas las pruebas salvo las marcadas `@pytest.mark.red` (el único fetch real de Yahoo, tolerante a fallos) y limpia las cachés de `marketpulse` entre pruebas. La BD de pruebas la fija el mismo `conftest.py` (nunca `inversor.db`). Regla de la casa: no digas "funciona" sin correr esto y mostrar la salida.

## Arquitectura
- `app/main.py` — arma la FastAPI (`include_router`) y sirve el frontend.
- `app/routes/` — endpoints por dominio: `profile.py` (perfil de riesgo; app de un solo usuario, sin login), `portfolio.py` (cartera, efectivo, importación y foto de Hapi, validación), `market.py` (precios y fundamentales manuales, por foto o desde la SEC; pulso de mercado y niveles por acción), `trades.py` (libro de órdenes y reconciliación de costo), `ai.py` (consultas a Luna; aplica la regla del plan: con el ETF bajo su meta, la intención de comprar acciones individuales se responde determinista sin llamar al proveedor), `decisions.py` (análisis, `trade_check` + segunda opinión de Luna — `trade_check` aplica la misma `regla_plan` como check `meta_etf` vinculante y exime a los ETF de índice amplio (`ETF_META`) de los límites por empresa/sector, y a sus compras del máximo por operación —, decisiones, riesgo, candidatos, alertas, diario, panel), `radar.py` (radar de oportunidades: GET solo lee lo guardado; POST refresh/{ticker} descargan precio Yahoo + 10-K SEC), `system.py` (límites, borrado total — incluye `contributions`), `marcador.py` (Fase 1: `GET /api/marcador` con marcador de bolsillo, fantasma del ETF del plan, alcancía y los tres avisos del plan; `GET /api/brecha` ficha de brecha solo-lectura; `PUT /api/plan` fija el ETF del plan; `GET /api/alcancia` devuelve solo la alcancía; `POST /api/flows/draft` + `/confirm` para movimientos por texto/captura/historial con fingerprint de duplicados; `GET/DELETE /api/flows`).
- Modo plan: `brecha.modo_plan` + `routes/marcador.py` (`modo_plan_estado`, dependencia `bloquear_en_modo_plan` → 409). Consultarlo siempre como `MARC.modo_plan_estado` (un solo monkeypatch; fixture `sin_modo_plan` en conftest). `GET /api/metricas` mide el plan.
- `app/cuerdas.py` — límites y perfil: endurecer al instante, aflojar con 7 días y motivo en el Diario; leer siempre con `limites_efectivos` / `perfil_efectivo`.
- `app/deps.py` — dependencias compartidas (`conn_dep`, `current_user`, `_photo_input`, `DISCLAIMER`).
- `app/ai_provider.py` — capa única del proveedor de IA: configuración (`.secrets/ai.env` o env `INVERSOR_AI_*`), endpoint, armado del cuerpo y extracción de respuesta. Ningún otro módulo habla con el proveedor.
- `app/photosync.py` / `fundsync.py` / `tradesync.py` / `flowsync.py` — extracción por foto o texto (cartera / fundamentales / órdenes / movimientos de dinero: depósitos, retiros, dividendos, ahorro en soles) con prompts propios y validación estricta; en flujos solo entra el estado «Terminado».
- `app/scoreboard.py` / `app/alcancia.py` / `app/brecha.py` — puros, sin BD ni red: marcador de bolsillo (depósitos netos + costos de depósito calculados con el tc de mercado del día o estimados con la tarifa, nunca con el tc implícito), fantasma SPY con `adjclose`, la alcancía EOQ (meta práctica en soles, progreso con sobrante acumulable) y la regla del plan (`regla_plan`, R1′; solo `ETF_META` cuenta para la meta — QQQ/DIA se tratan como acción — y solo ETF verificados) + brecha ETF (`brecha_usd` = venta para rebalancear; `dinero_nuevo_para_meta_usd` = aportes necesarios, el doble con meta 50 %) + proyección de rutas.
- `app/ai_assistant.py` / `ai_review.py` — consultas a Luna, revisión de tesis, explicación de decisiones y segunda opinión de operaciones (`trade_opinion`, con `ungrounded_numbers` para rechazar cifras ajenas al JSON).
- `app/marketdata.py` — precios de Yahoo Finance (sin clave) + indicadores. `fetch_history` trae `high/low`; `atr14` y `technical_summary(rows, price, day_change_pct)` producen `niveles` (stop −2·ATR, toma parcial +3·ATR, zona de entrada, semáforo de la acción, tipo de día). Siempre «regla técnica, no predicción».
- `app/marketpulse.py` — pulso de mercado (`pulse`/`cached_pulse`, 15 min) sobre SPY, QQQ, IWM, ^VIX, USO, TLT, GLD → semáforo normal/cauteloso/miedo, tipo de día y lectura determinista; `cached_levels` (10 min) por ticker y `_clear_cache()` para pruebas. Endpoints en `routes/market.py`: `GET /api/market/pulse`, `GET /api/levels/{ticker}`. `trade_check` añade `niveles` y `mercado_hoy` (None si Yahoo falla); `ai_assistant.context_for_user` añade `mercado_hoy` y `niveles` por posición (todo en try/except: Luna nunca falla por Yahoo).
- `app/secdata.py` — fundamentales del último 10-K desde SEC EDGAR (`companyfacts`, sin clave; ETF/fondos no aplican → 404). User-Agent propio (`INVERSOR_SEC_USER_AGENT` opcional). `extract_fundamentals` es pura; nunca estima ni mezcla presentaciones.
- `app/analysis.py` — scores fundamentales, múltiplos, DCF por escenarios.
- `app/radar.py` — universo fijo de 78 emisoras de EE.UU. con 10-K (sin ETF ni 20-F) y `screen()` pura: calidad media de los scores + margen de seguridad del DCF base con crecimiento del 10-K acotado a 0–15 % → veredicto.
- `app/risk.py` — concentración, correlación, límites, estrés.
- `app/decisions.py` — motor de decisiones y checklist de "promediar a la baja".
- `app/db.py` — esquema SQLite (12 tablas, incl. `contributions`) y utilidades de datos; `local_user_id()` da el usuario único.
- `run_local.py` + `iniciar-local.cmd` — lanzador local (puerto libre + navegador).

## Qué NO tocar
- `inversor.db` y `.secrets/` — datos y credenciales fuera de Git (en `.gitignore`). No los subas.
- El principio del producto: nunca inventar cifras, todo dato lleva fuente y fecha, nunca ejecutar órdenes. Si un cambio rompe eso, avisa antes.

## Notas
- Variable de entorno opcional: `INVERSOR_DB` (ruta de la base de datos).
- La API de Yahoo puede cambiar sin aviso; por eso existe el ingreso manual de precios.
- Los endpoints se sirven con `Cache-Control: no-cache` para que el navegador nunca muestre un frontend viejo.
