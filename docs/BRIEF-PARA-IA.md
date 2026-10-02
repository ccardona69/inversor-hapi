# BRIEF para IA asesora — guía derivada (NO es spec)

**Autoridad:** `docs/BRIEF.md` es la especificación congelada y `README.md` la doc
funcional. Esta guía es un resumen derivado para asesorar a una IA externa que
**no puede leer el repositorio**. Si algo aquí contradice a la spec, gana la spec.

**Trazabilidad:** contenido verificado contra el código el **2026-10-01** por el
agente del proyecto (HEAD `6a400a7` + cambios de blindaje pendientes de commit en
ese momento). La IA asesora no inspeccionó el código: estas afirmaciones son
"verificadas por el agente", no auditables por ella.

**Sin secretos:** este documento omite deliberadamente dominios, IPs, tokens y
cualquier enlace de acceso válido.

---

## 1. Qué es y qué no es

Herramienta **personal, de un solo usuario (sin login)** de apoyo a decisiones de
inversión para Hapi (bróker peruano, acciones EE.UU.). **Propone, argumenta y
registra; nunca ejecuta, reasigna ni opera.** El norte es medir la verdad y hacer
respetar el plan; la rentabilidad se busca dentro de esos límites, no por encima.

## 2. Invariantes no negociables

- Toda cifra lleva **fuente y fecha**; lo ausente se declara, nunca se inventa.
  Categorías: HECHO / CÁLCULO / ESTIMACIÓN (estimación = supuestos mostrados,
  jamás relleno de huecos).
- Todo flujo con IA es **borrador → confirmación humana**.
- Solo movimientos **"Terminado"** alimentan el marcador.
- Fingerprint de duplicados (`kind|fecha|monto`) detecta, **no bloquea**.
- `puesto_bolsillo = (depósitos − retiros) + costos_deposito`; tc de depósito
  **de mercado del día, jamás implícito** (`normalize_tc` acepta USD/PEN o
  PEN/USD y descarta fuera de [2.5, 5]); sin tc → tarifa ~$3 como ESTIMACIÓN.
- Ahorro en soles **no es depósito**; alimenta la alcancía aparte.
- Solo ~$3/depósito entra al marcador (comisiones vienen netas; dividendos ya
  están en el valor actual).
- Fase 1 **congelada**: cambios se discuten antes de codificar; Fase 2 exige
  gate conductual de 4 semanas de rutina cumplida.

## 3. Arquitectura verificada

**Stack:** FastAPI + SQLite (WAL) + Python. SPA sin dependencias
(`static/index.html|app.css|app.js`). Deps: `fastapi uvicorn pytest httpx`.

`app/`:

- `main.py` — arma la app; middleware `host_origin_guard`: Host debe estar en
  `INVERSOR_ALLOWED_HOSTS` (default `127.0.0.1,localhost,::1`) y las mutaciones
  exigen `Origin`/`Referer` propio → 403. Barrera web en ausencia de login.
- `db.py` — 12 tablas (`users`, `positions`, `trades`, `trade_sources`, `cash`,
  `prices`, `fundamentals`, `journal`, `decisions`, `candidates`, `settings`,
  `contributions`). `backup_db()`: **VACUUM INTO** + rotación a `backups/`
  (snapshot íntegro, incluye el WAL).
- `ai_provider.py` — **única puerta a la IA**. `request(..., client=None)`:
  red real solo si `client is None`. Config: `.secrets/ai.env` o `INVERSOR_AI_*`.
- `ai_review.py` — contratos JSON estrictos: `challenge` (3 contraargumentos a
  tesis; sin cifras ni verbos de acción), `explain` (parafrasea decisión del
  motor; cero números; no puede contradecirla), `trade_opinion` (`{resumen,
  a_favor, en_contra, vigilar}` validado con `ungrounded_numbers`, 1 reintento).
  **Luna opina; el motor decide. La IA no emite veredictos ejecutables.**
- `ai_assistant.py` — chat con contexto (posiciones, precios, riesgo, perfil,
  fundamentales, tesis).
- `marketdata.py` — Yahoo chart API **no oficial**: precio con fuente/fecha/
  estado (actual/reciente/desactualizado), histórico, SMA/RSI/volatilidad/
  drawdown, `atr14`, `technical_summary` → niveles (stop −2·ATR, parcial
  +3·ATR, zona de entrada, semáforo). "Regla técnica, no predicción".
- `marketpulse.py` — pulso (SPY/QQQ/IWM/^VIX/USO/TLT/GLD → semáforo + tipo de
  día + lectura determinista). Caché 15/10 min; degrada a `null` sin romperse.
- `secdata.py` — SEC EDGAR `companyfacts`, último **10-K** únicamente. ETF y
  emisoras 20-F (p.ej. TSM, ASML) → **404 por diseño**. `extract_fundamentals`
  pura; nunca estima ni mezcla presentaciones.
- `analysis.py` — scores 0–10, múltiplos, DCF **3 escenarios** (rangos,
  supuestos editables; nunca precio objetivo).
- `risk.py` — pesos, HHI, sectores, correlación por **grupos conocidos** (no
  covarianzas), límites configurables, estrés −10/−20/−30/−50 %.
- `decisions.py` — motor determinista + checklist obligatorio para promediar a
  la baja.
- `scoreboard.py` / `alcancia.py` — **puras** (sin BD ni red): marcador de
  bolsillo, fantasma SPY a retorno total (`adjclose`), alcancía EOQ.
- `radar.py` — universo fijo de **78 emisoras US con 10-K** + `screen()` pura →
  veredictos `barata_y_buena / precio_justo / buena_pero_cara / cuidado /
  faltan_datos`.
- `photosync / fundsync / tradesync / flowsync` — extracción por foto o texto,
  siempre a borrador.
- `routes/` — `profile, portfolio, market, trades, ai, decisions, radar,
  system (incluye borrado total), marcador`.

**Regla del plan (determinista, fuente única):** `scoreboard.plan_breach` +
`etf_pct`. Con el ETF bajo su meta (default 50 %): en el chat, la intención de
comprar acciones individuales se responde **sin llamar a la IA**
(`routes/ai.py` → `plan_guard`); en `trade_check` la evaluación declara la
brecha en `operacion.plan` (`etf_pct`, `etf_target_pct`, `faltan_usd`, aviso)
sin bloquearla. Sin dato de ETF la regla es **fail-closed** (cuenta como bajo
la meta).

## 4. Cobertura real del pipeline de datos

**Hay:** precios Yahoo con fuente/fecha · fundamentales 10-K de SEC EDGAR (solo
emisoras US) · fundamentales manuales o por foto (borrador→confirmación) ·
movimientos de dinero por texto/captura/historial · niveles ATR · pulso.

**No hay:** fundamentales de ETF ni 20-F · correlaciones calculadas ·
multi-divisa completa (MVP asume USD y lo declara) · precios garantizados en
vivo · ejecución · credenciales de Hapi.

## 5. Estado fechado (snapshot 2026-10-01 — se degrada con el tiempo)

- **Cartera:** ~$1 012 = AMZN ~55 % + GOOG ~45 %, ambas en rojo leve (~−4 %).
  Cash ≈ $0. **ETF: 0 %** frente a meta congelada 50 %. Depósitos netos
  ~$949 (9 "Terminado"); costos ~$27 ESTIMACIÓN.
- **Radar:** solo AMZN y GOOG tienen fundamentales cargados → ambos
  `buena_pero_cara` (MoS negativo vs DCF base). Resto del universo:
  `faltan_datos`.
- **Alcancía:** meta práctica S/480 ≈ $135; faltan ~5 meses (cadencia ~6 m).
- **Veredicto vigente del sistema:** próximo aporte → 100 % SPY/VOO. No hay
  espacio matemático para acciones individuales bajo la regla del plan.
- **Despliegue:** VPS AWS EC2 (ARM64, Ubuntu), systemd con auto-reinicio, IP
  elástica fija, Caddy con HTTPS automático (dominio `sslip.io` de esa IP) y
  **cookie-gate** por magic link (sin cookie → 404). SG: 80/443 mundo, 22 solo
  IP del dueño.
- **Pruebas:** `pytest tests/ -q` → 285 verdes; la suite bloquea Yahoo
  (`_fetch_json`), SEC (`_get` sin cliente) e IA (`request` sin cliente). La
  única prueba de red real (`@pytest.mark.red`) queda **fuera del default**
  (`pytest.ini`) y corre con `-m red`. Frontend: `node --check` + `node --test`.

## 6. Ya resuelto (no reportar como carencia)

Backups íntegros (VACUUM INTO) · SMA/RSI/volatilidad/drawdown · candado
Host/Origin · suite sin red real (Yahoo+SEC+IA) · prueba `red` fuera del
default · veredicto `faltan_datos` · regla ETF determinista · fantasma SPY ·
fingerprint de duplicados · reconcile de costo con doble confirmación ·
`ungrounded_numbers` · regla del plan con **fuente única** (`SB.plan_breach`)
compartida por chat y `trade_check`.

## 7. Backlog Fase 2 (candidatos — NO presentes; exigen gate conductual)

Asignador de próximo aporte · campo `dictamen` enum en `trade_opinion` · costo
de cambio descompuesto (a + b·Q) + "fantasma de cambio" · vigilante estate tax
(>$60 k → UCITS) · VOO como fantasma · metas 50/25/25 · tasa de ahorro como
métrica principal · canon SEN + fuzzy match Apex · huella UNIQUE + 409.

Descartados explícitos: ejecución automática · integración directa con Hapi ·
Monte Carlo · XIRR · Kelly · CVaR · DCA por niveles · predicciones ·
correlaciones calculadas (v2).

## 8. Reglas de asesoría para la IA externa

- Clasifica cada afirmación: **hecho verificado** (este doc) / **hecho
  reportado** (lo dijo el usuario) / **inferencia** / **recomendación**.
- Antes de diseñar sobre un dato, confirma que el pipeline lo cubre (§4).
- Propuestas de spec → backlog Fase 2, marcadas como tales; nunca como
  funcionalidad presente ni ejecutable hoy.
- Prohibido: ejecución o reasignación automática, proyecciones de precio,
  catalizadores inventados, probabilidades sin sustento, lenguaje de venta
  ("la próxima X", "retornos exponenciales"), y tratar salidas de Luna como
  veredictos.
- "Datos faltantes" bloquean una evaluación; no declaran malo al activo.

## 9. Mantenimiento de esta guía

Actualizar solo con cambios **aprobados y verificados en código**; registrar la
fecha (y commit si existe) de cada actualización; mantener §5 como snapshot
fechado, nunca como estado presente eterno; y no incorporar nunca dominios,
IPs, tokens ni enlaces de acceso válidos.
