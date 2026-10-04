# BACKLOG_FASE2.md — Inversor Hapi IA

Trabajo diferido a Fase 2. Requiere el gate conductual de `AGENTS.md` §15
(P0 completo + 4 semanas consecutivas de rutina + 0 desvíos sin documentar).
Todo lo que toca esquema vive aquí: v1.1 no cambia esquema.

---

## Prioridad 1 — Bitácora append-only

Bitácora inmutable de decisiones y aportes. Todo lo demás depende de esto.
Candidatos de diseño (decidir en Fase 2): tabla con `INSERT`-only (sin
UPDATE/DELETE por política), hash encadenado por fila, export firmado.
Trampa conocida: un trigger `INSTEAD OF UPDATE` que lanza error también
bloquearía migraciones — documentado en el blueprint.

## Prioridad 2 — Cumplimiento y vínculos

- Vínculo decisión–operación (qué `trade_check`/`decision` precedió a cada
  movimiento real en Hapi).
- Medición de cumplimiento hacia adelante (la tabla `trades` hoy está vacía;
  el juicio retroactivo es inválido sin ella).
- Detector de desviaciones: snapshot de posiciones en settings vs captura nueva;
  desviación = operación sin decisión registrada.

## Prioridad 3 — Riesgo y medición

- Estrés por activo con drawdown histórico propio y ventana declarada
  (reemplaza el estrés uniforme −50 %, hoy rotulado ilustrativo).
- Look-through del ETF en el HHI (hoy el ETF cuenta como una sola unidad).
- Propagación de etiqueta más débil de punta a punta (P3.3 si no se cerró en
  v1.1): `resultado_real` del marcador sigue sin etiqueta propia.
- `max_trades_per_month` (default 8, `app/risk.py:5`; validado en
  `app/cuerdas.py:27`) no se aplica en `trade_check`
  (`app/routes/decisions.py`): es un límite declarado, no vinculante (HV por
  búsqueda, 2026-10-04). No se toca por el congelamiento de D-13 (D-14).
- Satélite de 5 % solo para posiciones nuevas, vía GC (D-14): hoy el motor
  aplica un único «Máximo por empresa» a todo lo que no es ETF
  (`app/routes/decisions.py:338-341`); las posiciones heredadas (AMZN, GOOG)
  no deben quedar en incumplimiento permanente.

## Prioridad 4 — Reconciliación y fiscal

- Reconciliación con estado de cuenta Hapi (lado a lado posiciones/cash).
- Módulo fiscal verificado con contador: retención 30 % dividendos (HR),
  estate tax sobre USD 60k (HR — verificar umbral), impuesto en Perú
  (SIN DATO — se declara en toda proyección de rebalanceo).
- Reconstrucción histórica de costos de depósito: solo si aparecen los estados
  de Interbank (hoy SIN DATO irrecuperable, ver `AGENTS.md` §4 y D-04).

## Prioridad 5 — Infraestructura y selección (solo si el gate pasó)

- Rediseño de radar/pulso subordinado al plan (hoy el radar tiene 2.6 % de
  cobertura de fundamentales — candidato a congelarse por kill criterion).
- Autenticación más robusta que el enlace de entrada estático.
- Migración a UCITS si el portafolio se acerca a USD 60k (HR — verificar).
- Presupuesto de complejidad y revisión trimestral del sistema.

---

*Criterio de ingreso a Fase 2: nada de esta lista se implementa antes del gate.
Si la rutina no se establece en 8 semanas, el sistema se reduce a ficha del
plan, alcancía y marcador (`AGENTS.md` §13).*
