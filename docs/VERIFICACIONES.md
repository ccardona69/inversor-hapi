# VERIFICACIONES.md — Inversor Hapi IA

Historial de verificaciones solicitadas (VAs) con respuesta y evidencia
`file:line`. Nueva entrada = fecha + tabla. Etiquetas según `AGENTS.md` §2.

---

## VA-01 a VA-16 — respondidas 2026-10-01 (contra 37fc4bc + working tree)

| ID | Verificación | Respuesta | Evidencia | Estado |
|---|---|---|---|---|
| VA-01 | ¿`decisions.py` y el endpoint de análisis consultan `regla_plan`? | Chat (`plan_guard`) y `trade_check` sí; `POST /api/analysis/{t}` no — es descriptivo | `app/routes/decisions.py:55-142`, `app/ai_assistant.py:74`, `app/routes/decisions.py:274` | Gap → P1.3 |
| VA-02 | ¿Qué endpoints modifican `etf_target_pct` u otros parámetros del plan? | Ninguno escribe `etf_target_pct`. `PUT /api/limits` y `PUT /api/profile` aceptan cualquier valor sin validación ni rastro | `app/routes/decisions.py:393-397`, `app/routes/profile.py:17-22` | Gap → P6 |
| VA-03 | ¿`etf_pct` sin precio? ¿Excluye del denominador? | Excluye solo las que no tienen ni precio ni `hapi_value` de captura. `trade_check` bloquea con 400 si falta valor | `app/routes/portfolio.py:53-62`, `app/routes/decisions.py:72-75` | Parcial → P3.1 |
| VA-04 | ¿Rechazo de precios viejos? ¿TTL? | Sí hay TTL: ≤24 h «actual», ≤5 d «reciente», >5 d no usable. El respaldo a `hapi_value` de captura no caduca | `app/marketdata.py:75-95`, `app/routes/portfolio.py:56-60` | Parcial → P3.2 |
| VA-05 | ¿El marcador etiqueta estimaciones? | `costos_etiqueta` sí propaga; `resultado_real` no lleva etiqueta propia | `app/scoreboard.py:121,132,127,135` | Parcial → P3.3 |
| VA-06 | ¿El fantasma SPY replica costos y fechas reales? | Usa USD 0.15 fijo por compra simulada y retención 30 % sobre dividendos; no replica el costo real de cada depósito | `app/scoreboard.py:138` | Documentar |
| VA-07 | ¿`plan_guard` cómo detecta intención? ¿Tests de evasión? | Regex de verbos de compra + ticker en mayúsculas `[A-Z]{1,5}` con lista de exclusión. Evadible por reformulación («me animo con NVDA») o minúsculas; sin tests de evasión | `app/ai_assistant.py:41-44,73` | Gap → P4.2 |
| VA-08 | ¿Magic link: entropía, expiración, un solo uso, flags, revocación? | Ruta de entrada estática; cookie 1 año con HttpOnly+Secure+SameSite=Lax; no es de un solo uso; revocar = editar Caddyfile. Mitigado: uvicorn solo en loopback | Caddyfile del VPS; `run_local.py:12` | Media → P4.7 |
| VA-09 | ¿Backups: dónde, cuándo, restore probado? | `VACUUM INTO` a `backups/` en el mismo disco, rotación 10. Primera copia fuera del VPS: 2026-10-02 a PC local (sin cifrar — pendiente P4.8). Restore verificado en la copia | `app/db.py:132-157`, `app/routes/system.py:22-28` | Parcial → P0.6-7, P4.8 |
| VA-10 | ¿Base del snapshot §7? | VPS (canónica) | `/api/brecha` en VPS, 2026-10-02 00:20 UTC | Resuelto |
| VA-11 | ¿`delete_all`: backup previo, confirmación, Origin? | Confirmación literal «ELIMINAR» y Origin/Referer por middleware; sin backup automático previo | `app/routes/system.py:38-46`, `app/main.py` | Gap → P0.8 |
| VA-12 | ¿Rango histórico a Yahoo? | `fetch_history` por defecto `1y`; fantasma pide `5y`; cotización `5d` | `app/marketdata.py:31,47`, `app/routes/marcador.py:39` | Resuelto |
| VA-13 | ¿Comisión USD 3 por transacción, siempre? | `deposit_fee` = USD 3 fijo por depósito, solo como ESTIMACIÓN. Medido en BCP: USD 2.99 por transferencia (4/4). La meta de ≈ S/480 sale del EOQ | `app/scoreboard.py:16,99-101`, `app/alcancia.py:15-16,61-62` | Resuelto |
| VA-14 | ¿Contexto exacto al proveedor IA? ¿Política? | ≤40 posiciones (con fuente/fecha de precio), ≤20 fundamentales (campos permitidos), ≤5 tesis, ≤10 propuestas, ≤15 alertas, pulso, plan, límites, perfil de riesgo. Sin credenciales. Sin política de datos declarada ni tope de gasto | `app/ai_assistant.py:149-208`, `app/ai_provider.py:164,202` | Gap → P4.5-6 |
| VA-15 | ¿`etf_pct` con qty×precio o `hapi_value`? | qty × último precio usable; si no hay, `hapi_value` de la captura rotulado «verificar». Si difieren, `/api/validate` reporta la inconsistencia | `app/routes/portfolio.py:54-57,309` | Resuelto |
| VA-16 | ¿«Operación ≤10 %» aplica a compras de ETF_META? | Sí aplicaba y contradecía la regla (aporte ≈ 13.3 % del total salía «no cumple»). Corregido 2026-10-01: compras de ETF_META exentas; ventas de ETF siguen limitadas | `app/routes/decisions.py:295-303`; `tests/test_trade_check.py` | Corregido |

---

## Formato para futuras verificaciones

| Campo | Contenido |
|---|---|
| ID | VA-nn correlativo |
| Fecha | Cuándo se respondió |
| Base | Commit + working tree o VPS |
| Respuesta | Con evidencia `file:line` |
| Etiqueta | HV / HR / INF / CÁLC / EST / SIN DATO |
| Estado | Resuelto / Parcial / Gap → paquete |
