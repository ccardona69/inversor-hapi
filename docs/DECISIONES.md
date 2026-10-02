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
- **Reversión:** revertir el commit correspondiente en `static/app.js`.
