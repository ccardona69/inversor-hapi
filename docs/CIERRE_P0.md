# CIERRE_P0.md — Acta de cierre del paquete P0 (G0 «suelo reproducible»)

Fecha: 2026-10-02 · Base verificada: HEAD `60e9a3b` = tag `v1.1-base` =
`origin/master`. Etiquetas según `AGENTS.md` §2.

## 1. Checklist de aceptación P0

| ID | Acción | Estado | Evidencia | Etiqueta |
|---|---|---|---|---|
| P0.1 | Working tree commiteado o descartado | Cumplido | `git status` limpio en `60e9a3b` | HV |
| P0.2 | Tag del commit desplegado | Cumplido | `v1.1-base` → `60e9a3b` | HV |
| P0.3 | Diff contra `37fc4bc` | Cumplido | Informe en §2 de este documento | HV |
| P0.4 | Tests verdes en HEAD limpio | Cumplido | `pytest tests/ -q`: 313 verdes, 1 deseleccionada (`@pytest.mark.red`, fetch real); `compileall app` OK; `node --check static/app.js` OK; `node --test tests/frontend.test.js` 2/2 | HV |
| P0.5 | VPS como base canónica | Cumplido | `docs/DECISIONES.md` D-03 | HR |
| P0.6 | Backup off-site cifrado | Cumplido | D-05: copia en PC local con AES-256-CBC; clave entregada al usuario, fuera del repo y del VPS | HR |
| P0.7 | Restauración probada | Cumplido | `docs/VERIFICACIONES.md` VA-09: `integrity_check` OK tras descifrar la copia | HR |
| P0.8 | `delete_all` con backup previo | Cumplido | `app/routes/system.py:63-72`: exige `confirm="ELIMINAR"` y ejecuta `backup_db()` antes de borrar | HV |
| P0.9 | Hash desplegado visible | Cumplido | `GET /api/system/version` → `{"version": "v1.1-base", "fuente": "git describe --tags --always --dirty", "etiqueta": "HV"}` (`app/routes/system.py:36-53`); footer de la SPA muestra «build v1.1-base» (`static/app.js:203,219`) | HV |

Nota: el snapshot de `AGENTS.md` §4 reportaba 312 tests; en `v1.1-base` son 313.

## 2. Informe de diferencias `37fc4bc` → `60e9a3b` (`v1.1-base`)

5 commits, +1300/−216 líneas en 19 archivos. Sin cambio de esquema (respeta la
regla «v1.1 no cambia esquema»).

### Código (`app/`)

- `app/scoreboard.py` — `ETF_META` (lista cerrada de ETF de índice amplio);
  `etf_meta_value()` cuenta solo ETF **verificados**; `etf_pct()` fail-closed
  en ambos sentidos: el numerador excluye ETF sin verificar y el denominador
  incluye toda posición con precio, verificada o no.
- `app/brecha.py` — `regla_plan` con `ETF_META`; `brecha_usd` (venta necesaria
  para rebalancear) y `dinero_nuevo_para_meta_usd` (aportes necesarios sin
  vender); proyección de rutas comparables.
- `app/routes/decisions.py` — `trade_check` consulta `regla_plan` como check
  vinculante `meta_etf`; los ETF de `ETF_META` quedan exentos de los límites
  por empresa/sector; las **compras** de `ETF_META` quedan exentas del máximo
  por operación (corrección VA-16); las ventas de ETF siguen limitadas.
- `app/routes/marcador.py` — `PUT /api/plan` valida el ETF contra `ETF_META`;
  `GET /api/brecha` expone `dinero_nuevo`/`evaluable`.
- `app/routes/system.py` — `GET /api/system/version` (lee `git describe` del
  checkout) y backup automático antes de `delete_all`.

### Gobierno (`docs/` + `AGENTS.md`)

- `AGENTS.md` v1.0 adoptado como gobierno vinculante.
- `docs/AUDITORIA_v1.1_ULISES.md` — auditoría externa y paquetes P0–P7.
- `docs/PLANOS_DE_LA_CASA.md` — blueprint (renombrado desde
  `BRIEF-PARA-IA.md`).
- `docs/DECISIONES.md` — D-01 a D-05.
- `docs/VERIFICACIONES.md` — VA-01 a VA-16.
- `docs/BACKLOG_FASE2.md` — backlog Fase 2.

### Pruebas

+128 líneas en 5 archivos (`test_brecha`, `test_core`, `test_marcador_routes`,
`test_scoreboard`, `test_trade_check`), incluida
`test_aporte_del_plan_no_choca_con_maximo_por_operacion` (regresión de VA-16).

## 3. Lo que queda abierto (fuera de P0)

- **Decisión de plan AWS** — según el orden de `AGENTS.md` §14 va antes de P1.
  Free plan vence 2027-04-01 (HV, consola); escenarios comparables A–D en
  §5.2. Es decisión del usuario, no del agente.
- **Paquetes P1–P7** — pendientes de aprobación explícita por paquete
  (orden: P1 → P4 → P3 → P6 → P2 → P5).
- **SIN DATO heredados** — transferencias sin depósito registrado (verificar
  historial de rechazados en Hapi); pérdida tolerable real del perfil.
- **Gate conductual** (§15) — 4 semanas consecutivas con ≥ 1 `ahorro_soles` y
  0 desvíos sin documentar; corre por calendario, no por código.

## 4. Reversión

Este documento no cambia código ni datos. Revertir el commit que lo agrega
deshace el acta; el estado verificado permanece.
