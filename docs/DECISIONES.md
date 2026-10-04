# DECISIONES.md — Inversor Hapi IA

Registro de decisiones del usuario. Cada entrada: fecha, decisión, motivo,
reversión. Las decisiones se agregan al final; no se editan.

---

## D-01 — 2026-10-01 — AGENTS.md adoptado como gobierno

- **Decisión:** `AGENTS.md` v1.0 es vinculante; prevalece sobre `CLAUDE.md` y
  briefs, salvo `docs/BRIEF.md` (spec congelada).
- **Motivo:** reglas duras, taxonomía epistémica y compuertas G0/GC/G2 para
  cualquier agente que opere el repo, la base o el VPS.
- **Reversión:** editar el archivo requiere aprobación explícita del usuario.

## D-02 — 2026-10-01 — Corrección VA-16: límite por operación y ETF_META

- **Decisión:** las compras de ETF de índice amplio (`ETF_META`) quedan exentas
  del límite «máximo por operación» (10 %); las ventas de ETF siguen sujetas.
- **Motivo:** la compra que la regla del plan manda (aporte ≈ 13.3 % del total)
  salía «no cumple»; la regla se contradecía. La venta grande de ETF es el
  impulso que el plan quiere frenar.
- **Verificación:** `tests/test_trade_check.py`
  (`test_aporte_del_plan_no_choca_con_maximo_por_operacion`, venta de ETF
  sigue fallando el límite). 312 tests verdes.
- **Reversión:** revertir el commit que incluye `decisions.py:295-303`.

## D-03 — 2026-10-01 — Base canónica = VPS

- **Decisión:** la base de datos canónica es la del VPS; la local es copia de
  desarrollo.
- **Motivo:** la app vive desplegada; las fotos se cargan ahí.
- **Riesgo asumido:** la cuenta AWS es Free plan (cierra a los 6 meses o al
  agotar créditos; datos borrados 90 días después). Mitigación: backup fuera de
  AWS (D-05) + decisión de plan antes del vencimiento (fecha: SIN DATO).

## D-04 — 2026-10-01 — Costos históricos de depósito: EST permanente

- **Decisión:** aceptar que el costo real de los 9 depósitos históricos queda
  como estimación; hacia adelante, cada depósito se registra con `soles_amount`.
- **Motivo:** los soles salieron de Interbank y esa cuenta fue eliminada; el
  spread de «Yape Compra USD» es SIN DATO irrecuperable salvo el punto del
  24 ago (tc pagado 3.4695 vs mercado 3.3515).
- **Consecuencia:** `deposit_fee` sigue en USD 3 como piso declarado; el costo
  real probablemente es mayor (≈ USD 7.7 por aporte de USD 135 si el spread es
  ≈ 3.5 % — EST con una sola observación).

## D-05 — 2026-10-02 — Backup fuera de AWS

- **Decisión:** copia de la base canónica fuera del VPS, a la PC local.
- **Ejecución:** `backup_db()` (VACUUM INTO) en el VPS + descarga por SCP +
  verificación de integridad en la copia.
- **Pendiente:** cifrado de la copia (P4.8) y automatización periódica.
- **Actualización 2026-10-02:** la copia local está cifrada con AES-256-CBC
  (PBKDF2, 100k iteraciones). La clave se entregó al usuario una vez y no está
  guardada en el repo ni en el VPS. Automatización periódica sigue pendiente.

## D-06 — 2026-10-02 — Plan AWS: decisión pospuesta

- **Decisión:** no elegir aún entre escenarios A–C de §5.2 (Paid + t4g.small,
  Paid + t4g.micro, solo local + túnel); la decisión queda pendiente con fecha
  límite 2027-04-01 (vencimiento del Free plan, HV consola AWS).
- **Motivo:** margen de ≈ 6 meses; el backup cifrado fuera de AWS (D-05) ya
  elimina el riesgo urgente de pérdida de datos.
- **Reversión:** registrar la decisión elegida antes del 2027-04-01; una
  migración a local requiere su propia entrada y prueba de funcionamiento.

## D-07 — 2026-10-02 — Paquetes «Ulises» P1–P6 sin aprobar

- **Decisión:** ningún paquete aprobado por ahora; queda vigente el orden de
  evaluación P1 → P4 → P3 → P6 → P2 → P5.
- **Motivo:** el usuario prefiere revisar antes de autorizar implementación.
- **Estado:** pendiente. Cada paquete requiere aprobación explícita (regla
  dura 9); sin aprobación no se escribe código.

## D-06 — 2026-10-02 — Corrección de 4 bugs del frontend (E2E)

- **Decisión:** corregir los 4 bugs confirmados en la prueba de punta a punta
  de `static/app.js`, aprobados por el usuario («Sí, los 4 bugs»).
- **Bugs y corrección:**
  1. Campos numéricos invertían dígitos («100» → «001»): los 5 inputs pasan de
     `type="number"` a `type="text"` con `inputmode`, porque el caret de
     `type=number` no se restaura tras el re-render y saltaba al inicio. Los
     valores se limpian con `cleanNum` y el botón Guardar queda protegido
     contra NaN.
  2. Verificación contradictoria y sin control: una posición importada se
     mostraba «Verificado por ti» sin estarlo (`verified: persisted`). Ahora
     toda posición importada nace `verified: false`, como en el backend, y el
     detalle ofrece el botón «Marcar como verificada» que llama a
     `POST /api/positions/{ticker}/verify` (endpoint que ya existía).
  3. Sin precio se fabricaban cifras («$0.00», «−100 %»): tabla, detalle,
     tarjetas del resumen y snapshot muestran «Sin dato» cuando la posición
     no tiene cotización, y se elimina el cálculo local del resultado del
     marcador (`invested − puesto_bolsillo`) que usaba posiciones sin
     verificar; solo se muestra el `resultado_real` del backend.
  4. «Posiciones objetivo» no persistía: `saveSettings` solo enviaba
     `max_position_pct`. Ahora también envía `positions_target` en el mismo
     `PUT /api/limits` (el endpoint ya acepta claves arbitrarias) y se lee al
     cargar.
- **Verificación:** `node --check` + `node --test tests/frontend.test.js`
  (2 verdes) + `pytest tests/ -q` (313 verdes, 1 deseleccionado de red).
- **Ampliación (aprobada por el usuario):** si TODAS las posiciones están sin
  cotización, «Tu cartera vale hoy», «Invertido en posiciones» y «Tu cartera
  hoy» del marcador muestran «Sin dato» en vez de $0.00 (una suma de ceros
  también fabrica una cifra). En el detalle, la etiqueta ya no es solo
  «POR VERIFICAR»: sin verificar → «POR VERIFICAR»; verificada con precio
  vigente → «HECHO»; verificada con precio de captura/antiguo → «PRECIO POR
  VERIFICAR»; verificada sin precio → «SIN COTIZACIÓN» — así no contradice a
  «Verificado por ti».
- **Reversión:** revertir el commit correspondiente en `static/app.js`.

## D-08 — 2026-10-02 — Plan en una línea (Paso 0)

- **Decisión:** «Todo dinero nuevo va a SPY hasta que el ETF llegue al 50 % de
  la cartera». ETF elegido de forma explícita: SPY (era el valor por defecto).
  Se descartó SPYG: ≈ 53 % tecnología y ≈ 54 % en el mismo grupo correlacionado
  que AMZN/GOOG (HR, ficha SSGA 2026-09-01); no diversifica.
- **Rebalanceo:** no vender. La meta se alcanza solo con dinero nuevo (≈ 8
  aportes ≈ 4 años, EST a precios constantes). Impuesto en Perú: SIN DATO.
- **Acciones del usuario fuera del sistema (pendientes, HR al confirmarse):**
  persona de confianza con regla de 72 h para cualquier compra que no sea el
  ETF; transferencia automática del banco el día de pago; comparar tipo de
  cambio banco vs casas de cambio; preguntar a Hapi por depósitos directos en
  USD; alerta de presupuesto en Azure.
- **Actualización 2026-10-03 (investigación del agente, HR):**
  - Hapi sí acepta depósitos directos desde Perú: Cross Payments en **soles**
    (mín. USD 1.99 por depósito) y en **dólares** (0.45 %, mín. USD 2.99), y
    wire SWIFT internacional sin comisión de Hapi (el banco/intermediario
    puede cobrar; 1–3 días hábiles). Fuentes: help.hapi.trade
    (artículos 8976002, 12631400, 10244510), consultados 2026-10-03.
  - Casas de cambio online reguladas por la SBS (Rextie, Kambista, TuCambista,
    TKambio, Cambia FX): sin comisión explícita, spread ≈ 0.87 %
    (tipodecambio.pe, 2026-10-03) vs ≈ 3.5 % medido en «Yape Compra USD».
    Ruta alternativa ilustrativa para un aporte de ≈ USD 135: casa online
    (≈ USD 1.2 de spread) + Cross Payments USD (mín. USD 2.99) ≈ USD 4.2
    frente a los ≈ USD 7.7 actuales (EST). La conversión dentro de Cross
    Payments en soles tiene su propio tc: SIN DATO — compararlo en la app el
    día del depósito.
  - Alerta de presupuesto Azure: no creable sin acceso a la cuenta; pasos:
    Azure Portal → Cost Management + Billing → Budgets → Add (mensual) →
    acción «alert» con email. El tope de la app (30 llamadas/mes) ya corta el
    gasto por dentro.
  - Push a GitHub bloqueado: «You must verify your email address» (403). El
    usuario debe verificar el correo de la cuenta o empujar manualmente.
  - Despliegue al VPS bloqueado: no hay host/alias SSH documentado (regla 10:
    IP fuera del repo). El usuario puede ejecutar en el VPS:
    `git pull && sudo systemctl restart <servicio>` tras backup de la base,
    o entregar el host al agente.
- **Reversión:** nueva entrada con fecha y motivo.

## D-09 — 2026-10-02 — Modo plan (P1)

- **Decisión:** mientras el ETF esté bajo la meta (o sin dato), el sistema
  cierra las «sirenas»: radar, pulso, niveles ATR, DCF/técnica, Luna (chat,
  segunda opinión, explicación, cuestionar tesis) y fundamentales por red
  (409). Sin interruptor: se apaga solo al llegar a la meta. La lectura de
  capturas (cartera, movimientos, órdenes) sigue. «¿Compro o vendo?» llama a
  trade_check; una compra de acción se rechaza sin red. Se retira el texto fijo
  que se mostraba como «segunda mirada de Luna» con datos reales.
- **Consecuencia aceptada:** a la cadencia actual el modo plan dura ≈ 4 años.
- **Verificación:** `tests/test_modo_plan.py`; suite 353 verdes.
- **Reversión:** revertir los cambios en `app/brecha.py` (modo_plan),
  `app/routes/marcador.py` (bloquear_en_modo_plan) y las dependencias en
  radar/market/ai/decisions; `static/app.js`.

## D-10 — 2026-10-02 — Cuerdas: límites y perfil con enfriamiento (P6)

- **Decisión:** endurecer aplica al instante; aflojar espera 7 días, exige
  motivo y queda en el Diario (con fecha de revisión). Cancelar es inmediato.
  Claves y rangos validados (`app/cuerdas.py`).
- **Huecos conocidos:** primer valor de un campo de perfil vacío aplica al
  instante; `delete_all` borra settings sin enfriamiento.
- **Verificación:** `tests/test_cuerdas.py`.
- **Reversión:** revertir `app/cuerdas.py` y los PUT de limits/profile.

## D-11 — 2026-10-02 — Verificación con evidencia (P3)

- **Decisión:** se elimina `POST /api/positions/verify_all`. Verificar una
  posición exige un texto de evidencia (3–300) que queda fechado en `notes`.
- **Reversión:** revertir `app/routes/portfolio.py`.

## D-12 — 2026-10-02 — Tope duro de IA (P4)

- **Decisión:** 30 llamadas al mes, contadas antes de tocar la red en
  `ai_provider.request` (settings `ia_uso` / `ia_tope_mensual`, sin escritor
  por API). Se cuenta por llamada: el costo por token es SIN DATO.
- **Reversión:** revertir `consumir_presupuesto` en `app/ai_provider.py`.

## D-13 — 2026-10-02 — Medir y fijar el corte (Paso 3)

- **Decisión:** `GET /api/metricas` mide solo cuatro cosas: % de ETF, costo
  por depósito, % de compras (USD) al ETF desde 2026-10-02 y costo anual de la
  herramienta como % de la cartera (HR vía `PUT /api/metricas/costo_sistema`).
- **Congelamiento:** sin funciones nuevas hasta 6 depósitos seguidos al ETF.
- **Criterio de abandono:** revisión el 2027-01-02; si para entonces no se usa
  el día del depósito, se archiva y queda la versión mínima (hoja de 5 filas
  + un ETF).
- **AWS:** recordatorio de decisión de plan el 2027-03-01 (vence 2027-04-01,
  D-06).

## D-14 — 2026-10-04 — Prompt de la IA asesora v3.2

- **Decisión:** se adopta `docs/PROMPT_ASESOR.md` v3.2 (v3.1 del usuario + N1,
  N2, N3 y tres ajustes menores), subordinado a BRIEF, AGENTS, PLANOS y este
  registro. Se añade a AGENTS §11.
- **D-08 ratificada (N1):** no vender; la meta se alcanza solo con dinero
  nuevo. Rebalancear vendiendo deja de presentarse como ruta abierta.
- **C2 opción 1:** `barata_y_buena` (`app/radar.py:53,56,99`) se acepta como
  etiqueta técnica del radar; no se renombra.
- **Satélite de 5 %:** solo para posiciones nuevas, en Fase 2 vía GC. Hoy el
  motor tiene un único «Máximo por empresa» (`app/routes/decisions.py:338-341`).
  `max_position_pct` no se cambia.
- **Hallazgo anotado sin tocar (congelamiento D-13):** `max_trades_per_month`
  no se aplica en `trade_check`; anotado en `docs/BACKLOG_FASE2.md`.
- **G0:** árbol limpio; tag `pre-d14` sobre `a466970`; respaldo local
  `backups/inversor-20261004-122530.db` (VACUUM INTO, `integrity_check` ok).
  La base canónica del VPS no se tocó ni se respaldó en este paso (sin acceso
  SSH documentado, D-08); el cambio es solo documental.
- **Reversión:** `git revert` del commit de D-14, o nueva entrada con fecha y
  motivo.

