# Planos de la casa — guía para IA asesora (derivada, NO es spec)

**Autoridad:** `docs/BRIEF.md` es la especificación congelada. Este documento es
un **plano técnico derivado** para una IA asesora que **no puede leer el
repositorio**. Si algo aquí contradice a la spec, gana la spec.

**Trazabilidad:** verificado contra el código el **2026-10-02** por el agente
del proyecto. HEAD commiteado y desplegado: `37fc4bc`. Contenido adicional
aplicado y probado (311 tests verdes) pero **pendiente de commit**: lista
`ETF_META`, numerador de `etf_pct` solo-verificado, `dinero_nuevo_para_meta_usd`
y `evaluable` en `/api/brecha`, `PUT /api/plan` validando contra `ETF_META`.
La IA asesora no inspeccionó el código: estas afirmaciones son
"verificadas por el agente", no auditables por ella. Cuando una afirmación
dependa del tiempo, lleva fecha.

**Sin secretos:** este documento omite deliberadamente dominios, IPs, tokens,
cookies y cualquier enlace de acceso válido.

---

## 1. Qué es y qué no es

Herramienta **personal, de un solo usuario (sin login en la app)** de apoyo a
decisiones de inversión para Hapi (bróker, acciones EE.UU., residente en Perú).
**Propone, argumenta y registra; nunca ejecuta, reasigna ni opera.**
El norte es medir la verdad y hacer respetar el plan; la rentabilidad se busca
dentro de esos límites, no por encima.

Frase del proyecto: *"Transforma datos con fuente y fecha en decisiones
explicables."*

## 2. Invariantes no negociables

- Toda cifra lleva **fuente y fecha**; lo ausente se declara, nunca se inventa.
  Etiquetas: **HECHO / CÁLCULO / ESTIMACIÓN / sin dato**. Estimación = supuestos
  mostrados, jamás relleno de huecos.
- Todo flujo con IA es **borrador → confirmación humana** (`draft` → `confirm`).
- Solo movimientos **"Terminado"** alimentan el marcador.
- Fingerprint de duplicados (`kind|fecha|monto`) detecta, **no bloquea**.
- `puesto_bolsillo = (depósitos − retiros) + costos_deposito`; el tc del
  depósito es **de mercado del día, jamás el implícito de la fila**
  (`normalize_tc` acepta USD/PEN o PEN/USD y descarta fuera de [2.5, 5]);
  sin tc de mercado → tarifa configurada como ESTIMACIÓN.
- Ahorro en soles **no es depósito**; alimenta la alcancía aparte.
- Comisiones de trading ya vienen netas en Hapi; dividendos ya están en el
  valor actual. Solo el costo del depósito entra al marcador.
- **Fail-closed en el plan:** sin dato de exposición ETF, la regla cuenta como
  bajo la meta. Una acción sin verificar entra a la base; un ETF sin verificar
  NO entra al numerador.
- Luna opina; el motor decide. La IA nunca emite veredictos ejecutables.
- Fase 1 **congelada**: cambios se discuten antes de codificar; Fase 2 exige
  gate conductual de 4 semanas de rutina cumplida.

## 3. Arquitectura

**Stack:** FastAPI + SQLite (WAL, `busy_timeout`) + Python 3.
SPA sin dependencias (`static/index.html|app.css|app.js`).
Deps: `fastapi uvicorn pytest httpx`. Un solo usuario (`local_user_id`).

### 3.1 Módulos (`app/`)

| Módulo | Responsabilidad |
|---|---|
| `main.py` | Arma la app; middleware `host_origin_guard`: Host en `INVERSOR_ALLOWED_HOSTS` (default loopback) y mutaciones exigen `Origin`/`Referer` propio → 403 |
| `db.py` | Esquema (12 tablas), `PRAGMA user_version`, `backup_db()` = **VACUUM INTO** + rotación a `backups/` (snapshot íntegro, incluye WAL), `export_data`, `get_setting`/`set_setting` |
| `deps.py` | `conn_dep` (commit al final), `current_user`, `_photo_input`, `DISCLAIMER` |
| `scoreboard.py` | **Puro.** `marcador` (bolsillo), `fantasma_spy` (retorno total `adjclose`, descuenta retención 30 % de dividendos), `costo_deposito`, `normalize_tc`, `etf_pct`, `etf_meta_value`, `SETTINGS_DEFAULTS`, `ETF_TICKERS`, `ETF_META` |
| `brecha.py` | **Puro, fuente única de la regla del plan.** `regla_plan`, `brecha`, `proyeccion` (3 rutas), `es_etf` |
| `alcancia.py` | **Puro.** Alcancía EOQ: meta práctica en soles, cadencia, progreso con sobrante |
| `risk.py` | Pesos, HHI, sectores, correlación por **grupos conocidos** (no covarianzas), límites, estrés −10/−20/−30/−50 % uniforme |
| `decisions.py` | Motor determinista de decisión + checklist obligatorio para promediar a la baja |
| `analysis.py` | Scores fundamentales 0–10, múltiplos, DCF **3 escenarios** (rangos; nunca precio objetivo) |
| `marketdata.py` | Yahoo chart API **no oficial**: precio con fuente/fecha/estado, histórico `close`+`adjclose`+`high/low`, SMA/RSI/vol/drawdown, `atr14`, `technical_summary` → niveles (stop −2·ATR, parcial +3·ATR, zona entrada, semáforo). Regla técnica, no predicción |
| `marketpulse.py` | Pulso (SPY/QQQ/IWM/^VIX/USO/TLT/GLD → semáforo + tipo de día + lectura determinista). Caché 15/10 min; degrada a `null` |
| `secdata.py` | SEC EDGAR `companyfacts`, último **10-K** solamente. ETF y emisoras 20-F → **404 por diseño**. `extract_fundamentals` pura |
| `radar.py` | Universo **fijo** de 78 emisoras US con 10-K + `screen()` pura → `barata_y_buena / precio_justo / buena_pero_cara / cuidado / faltan_datos` |
| `ai_provider.py` | **Única puerta a la IA.** `request(..., client=None)`: red real solo si `client is None`. Config: `.secrets/ai.env` o `INVERSOR_AI_*` |
| `ai_review.py` | Contratos estrictos: `challenge` (contraargumentos, sin cifras), `explain` (parafrasea al motor; cero números nuevos), `trade_opinion` (`{resumen,a_favor,en_contra,vigilar}` + `ungrounded_numbers`, 1 reintento) |
| `ai_assistant.py` | Chat `ask` con contexto (cartera, precios, riesgo, perfil, tesis, pulso); `plan_guard` determinista ANTES del proveedor |
| `photosync / fundsync / tradesync / flowsync` | Extracción por foto o texto (cartera / fundamentales / órdenes / movimientos de dinero), **siempre a borrador** |

### 3.2 Modelo de datos (12 tablas, campos que importan)

| Tabla | Semántica |
|---|---|
| `positions` | `ticker, qty, avg_cost, invested, hapi_value, hapi_pl, verified, source` · `verified=0` al cargar por foto o manual; sube a 1 con `/verify` |
| `contributions` | `kind ∈ {deposito, retiro, dividendo, ahorro_soles}`, `amount_usd, soles_amount, fx_rate (informativo, jamás usado en costos), at, source, fingerprint` · INSERT + DELETE; sin UPDATE |
| `decisions` | `ticker, proposal JSON, user_choice, authorized, created_at` · INSERT + UPDATE (proposal al evaluar operación; choice/authorized al registrar) — **mutable hoy; la bitácora es Fase 2** |
| `trades` | `ticker, side, qty, price, fees, currency, at` · **0 filas en la BD real** — las posiciones llegaron por foto, no por órdenes importadas |
| `prices` | última cotización por ticker con `source`/`asof` |
| `fundamentals` | JSON por ticker con `source`/`asof` |
| `journal` | tesis + revisiones (`challenge` de Luna vive aquí) |
| `settings` | clave-valor JSON; los defaults **no se escriben por leerlos** |
| `cash` | una fila por moneda (`currency`, `amount`) |
| `candidates`, `trade_sources`, `users` | radar / importaciones / usuario único |

### 3.3 Mapa de endpoints (lo que escribe vs lo que solo lee)

**Solo lectura (GET):** `portfolio` `marcador` `alcancia` **`brecha`** `radar`
`risk` `decisions` `journal` `alerts` `dashboard` `settings` `flows` `trades`
`candidates` `profile` `market/pulse` `levels/{t}` `fundamentals/{t}`
`validate` `assistant/status` `hapi/photo/status` `system/export`.

**Escritura (POST/PUT/DELETE):**

| Endpoint | Escribe |
|---|---|
| `POST /api/trade_check` | decisiones (propuesta + `operacion_evaluada`); intenta SEC si faltan fundamentales; guarda cotizaciones refrescadas |
| `POST /api/analysis/{t}` | decisiones |
| `POST /api/decisions/{d}/record` | decisions.user_choice/authorized — **registro, nunca ejecución** |
| `POST /api/trade_check/{d}/luna` · `journal/{j}/challenge` · `decisions/{d}/explain` | llamadas a Luna con contrato estricto |
| `POST /api/assistant/ask` | chat; `plan_guard` puede responder sin IA; seguimiento guarda en journal |
| `POST /api/flows/draft` → `/confirm` | contributions (fingerprint detecta duplicados, `allow_duplicates` explícito) |
| `POST /api/positions` · `/{t}/verify` · `/verify_all` · `DELETE` | positions (`verified=0` al escribir) |
| `PUT /api/cash` · `/api/profile` · `/api/limits` | cash / settings.risk_profile / settings.limits |
| **`PUT /api/plan`** | `settings.etf_plan` — validado contra `ETF_META` |
| `POST /api/prices/*` · `/api/fundamentals/*` | prices / fundamentals (manual, foto, SEC) |
| `POST /api/trades/import` · `/{t}/reconcile` | trades (importación/reconciliación con doble confirmación) |
| `POST /api/radar/refresh` · `/{t}` | descarga precio Yahoo + 10-K SEC para el universo fijo |
| `POST /api/system/backup` · `settings/delete_all` | backup VACUUM INTO / borrado total (tupla literal de tablas) |

**Realidad del frontend (V-5):** `trade_check`, `/api/brecha` y `PUT /api/plan`
son **API-only hoy** — `static/app.js` no los invoca. La ficha de brecha no
tiene UI: mostrarla exige trabajo de frontend nuevo.

## 4. La regla del plan (fuente única: `brecha.regla_plan`)

**Meta:** `etf_target_pct` (default **50 %**, porcentaje no fracción) en ETF de
**índice amplio verificados**.

- `ETF_META = {SPY VOO IVV SPLG VTI ITOT SCHB SCHX VT ACWI VEA VXUS IWM RSP}`
  — lo único que cuenta para la meta, exime de límites y es válido en
  `etf_plan`. QQQ/QQQM/DIA **no** diversifican una cartera concentrada en
  megacaps: se evalúan como acción (la regla aplica, los límites aplican).
- `etf_pct` = `etf_meta_value / exposición con precio` · denominador: **todas**
  las posiciones con precio · numerador: solo `ETF_META` **verificados** ·
  `None` si nada tiene precio.

**Tabla de verdad de `regla_plan`:**

| Operación | `aplica` | Resultado |
|---|---|---|
| Comprar acción o ETF-no-meta, sin monto (chat) | sí | R1: cumple solo si `etf_pct ≥ meta` (None → no cumple) |
| Comprar acción o ETF-no-meta, con monto | sí | R1′: cumple solo si `etf_pct_después ≥ meta` |
| Comprar ETF_META | no | siempre cumple |
| Vender acción | no | siempre cumple |
| Vender ETF_META | sí | cumple + aviso si queda bajo la meta |

**Aplicación:** chat (`plan_guard`, responde sin IA) y `trade_check`
(**vinculante**: R1′ es el 5º check `meta_etf` dentro de `limites`;
`operacion.plan` lleva `etf_pct_antes/después`, `faltan_usd`, `aviso`).
Los ETF_META están exentos de los checks "Máximo por empresa" y "Máximo por
sector" — la meta 50 % supera el límite genérico de 25 % — y sus **compras**
del "Máximo por operación" (10 %): con una cartera chica el aporte del plan lo
excede. Las ventas de ETF siguen sujetas a ese límite.

**`GET /api/brecha`** (solo lectura): `brecha_usd` = venta para rebalancear hoy;
`dinero_nuevo_para_meta_usd` = brecha/(1−t) — por aportes hace falta **más**
que la brecha (cada USD nuevo también agranda la base; con meta 50 %, el doble);
`a_etf_usd`/`libre_usd` = reparto del dinero a invertir (`a_invertir` = efectivo
+ aporte nuevo); `evaluable:false` si hay posiciones pero ninguna tiene precio
(fail-closed: todo al ETF); `proyeccion` = 3 rutas (despacio / ahorrar más /
rebalancear) siempre ESTIMACIÓN; aviso de orden: lo «libre» solo existe después
de comprar la parte ETF.

## 5. Constantes que importan

`DEFAULT_LIMITS`: posición 25 % · sector 40 % · operación 10 % del total ·
reserva mínima $0 · ≤8 operaciones/mes · pérdida tolerable 30 %.
`SETTINGS_DEFAULTS`: `deposit_fee 3.0` · `r 0.05` (fracción anual) ·
`fx_default 3.55` · `etf_target_pct 50` (porcentaje) · `etf_plan "SPY"` ·
`ahorro_mensual_declarado 80` (estimación mientras haya <2 meses de datos).
Cuidado con las unidades: `r=0.05` es fracción, `etf_target_pct=50` es %.

## 6. Cobertura real del pipeline de datos

**Hay:** precios Yahoo con fuente/fecha · fundamentales 10-K SEC EDGAR (solo
emisoras US) · fundamentales manuales/foto (borrador→confirmación) ·
movimientos por texto/captura/historial · niveles ATR · pulso de mercado ·
tc de mercado diario vía `PEN=X` (close; no distingue compra/venta — spread
~0.2 % declarado).

**No hay:** fundamentales de ETF ni de emisoras 20-F · correlaciones calculadas
· multi-divisa completa (MVP asume USD y lo declara) · precios garantizados en
vivo · ejecución · credenciales de Hapi · ledger de órdenes (`trades` vacío:
nada que reconcilie posición↔aporte histórico) · look-through de ETF (un ETF
cuenta como una posición en HHI).

## 7. Estado fechado (snapshot 2026-10-02 — se degrada con el tiempo)

- **Cartera:** ~$1 012 = AMZN ~55 % + GOOG ~45 %. Cash ≈ $0. **ETF: 0 %** vs
  meta 50 %. `brecha_usd` ≈ $506 (venta para rebalancear);
  `dinero_nuevo_para_meta_usd` ≈ $1 012 (aportes necesarios).
- **Depósitos:** 9 "Terminado" ≈ $949 netos; **0 con `soles_amount`** → costo
  real histórico imposible (`cobertura_costo_real` 0/9; solo mejora hacia
  adelante). 1 `ahorro_soles`, 3 dividendos, ~14 decisiones.
- **Alcancía:** meta práctica ~S/480 ≈ $135; cadencia ~6 meses → llegar al 50 %
  por aportes toma ~8 aportes ≈ 3.5–4 años (ESTIMACIÓN, precios constantes).
- **Radar:** solo AMZN y GOOG tienen fundamentales → `buena_pero_cara`;
  resto `faltan_datos`.
- **Veredicto vigente:** próximo aporte → 100 % al ETF del plan. No hay espacio
  matemático para acciones individuales bajo la regla.
- **Despliegue:** VPS AWS EC2 ARM64 Ubuntu, systemd, IP elástica, Caddy HTTPS
  (dominio `sslip.io`), **cookie-gate** por magic link (sin cookie → 404) +
  `host_origin_guard` en la app. SG: 80/443 mundo, 22 solo IP del dueño.
  **Dos bases de datos existen** (local y VPS): la del VPS es la canónica.
- **Pruebas:** `pytest tests/ -q` → **311 verdes**, 1 deseleccionado; la suite
  bloquea Yahoo (`_fetch_json`), SEC e IA sin cliente; `@pytest.mark.red` (red
  real) fuera del default. Frontend: `node --check` + `node --test`.

## 8. Ya resuelto (no reportar como carencia)

Fuente única de la regla del plan compartida por chat y `trade_check` · regla
vinculante como 5º check · `ETF_META` separado de `ETF_TICKERS` · ETF solo
cuenta verificado · ficha de brecha con dinero-nuevo y `evaluable` ·
`PUT /api/plan` (una decisión fija destino de aportes y fantasma) ·
`cobertura_costo_real` · draft marca depósitos incompletos (costo quedará
ESTIMACIÓN) · backups VACUUM INTO · suite sin red real · cookie-gate +
Host/Origin · fantasma con retención 30 % ya descontada · fingerprint ·
reconcile con doble confirmación · `ungrounded_numbers`.

## 9. Backlog Fase 2 (candidatos — NO presentes; exigen gate conductual + G2)

Bitácora append-only de decisiones y aportes (triggers; **ojo:** un trigger con
nombre de columna equivocado se crea sin error y falla en el DELETE — generar
desde `PRAGMA table_info`; `delete_all` hoy borraría la bitácora) · vínculo
decisión↔operación y aporte↔destino · medición de cumplimiento hacia adelante
(con fecha de inicio de la regla; el pasado no se puede juzgar — `trades` vacío)
· tabla `asignaciones` · campo `dictamen` en `trade_opinion` · costo de cambio
descompuesto (a + b·Q) + fantasma de cambio · vigilante estate tax
(>$60 k → UCITS) · tasa de ahorro como métrica · canon SEN + fuzzy Apex ·
huella UNIQUE + 409 · look-through HHI de ETF · estrés por activo ·
swap acción→acción bajo meta (hoy bloqueado por R1′ — decisión del usuario).

Descartados: ejecución automática · integración con Hapi · Monte Carlo · XIRR ·
Kelly · CVaR · DCA por niveles · predicciones · correlaciones calculadas.

## 10. Reglas de asesoría para la IA externa

- Clasifica cada afirmación: **hecho verificado** (este doc) / **hecho
  reportado** (lo dijo el usuario) / **inferencia** / **recomendación**.
- Antes de diseñar sobre un dato, confirma que §6 lo cubre. Antes de proponer
  código, pide verificación `archivo:línea` al agente — este plano sustituye al
  código, no al commit.
- Gates: **G0** reproducible (commit+tag+backup) antes de todo · **GC**
  comportamiento sin schema → aprobación explícita · **G2** schema →
  aprobación + backup + migración reversible ensayada en copia.
- Propuestas de spec → backlog Fase 2 marcado como tal; nunca como
  funcionalidad presente ni ejecutable hoy.
- Prohibido: ejecución o reasignación automática, proyecciones de precio,
  catalizadores inventados, probabilidades sin sustento, lenguaje de venta
  ("la próxima X"), tratar salidas de Luna como veredictos, elegir por el
  usuario entre "llegar despacio / ahorrar más / rebalancear".
- "Datos faltantes" bloquean una evaluación; no declaran malo al activo.

## 11. Mantenimiento de esta guía

Actualizar solo con cambios **aprobados y verificados en código**; registrar la
fecha (y commit si existe); mantener §7 como snapshot fechado; no incorporar
nunca dominios, IPs, tokens ni enlaces de acceso válidos.
