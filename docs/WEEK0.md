# Semana 0 — Carga y validación con datos reales

Precondición: app abierta (`python run_local.py`) · extracto de Hapi a la mano
(con los **soles reales enviados** por depósito, no la tarifa publicada).

## Paso 1 — Reunir insumos (antes de tocar la app)

- [ ] 9 depósitos "Terminado": fecha · USD que llegó · soles reales enviados.
- [ ] Dividendos: NVDA $0.27 · GOOG $0.20 · SPYG $0.08. Retiros: ninguno.
- [ ] Valor de cuenta actual: $1,022.77 (de Hapi).

## Paso 2 — Cargar movimientos (borrador → confirmar)

- [ ] Pegar/subir el historial en la caja de la alcancía → revisar borrador →
      confirmar.
- [ ] Esperado: entran 9 depósitos + 3 dividendos; NO entran $80 "Creado" ni
      $20 "Expirado".
- [ ] **Pass:** `depositado_neto = $949.41`.

## Paso 3 — Reemplazar la estimación $3 por el costo real

- [ ] Por cada depósito, ingresar los soles reales → el costo pasa de
      ESTIMACIÓN ($3) a CÁLCULO (`soles / tc_mercado − usd_llegado`).
- [ ] Anotar el nuevo `costos_deposito` (será ≠ $27), y el nuevo
      `puesto_bolsillo` y `resultado_real`.
- [ ] Verificar cada costo contra el extracto, no contra la tarifa publicada.
- [ ] **Pass:** cada costo con etiqueta CÁLCULO + fuente/fecha del tc del día.

## Paso 4 — Validar duplicados con datos reales

- [ ] Reimportar el mismo historial → 0 duplicados nuevos
      (huella `tipo|fecha|coalesce(usd,soles)`).
- [ ] Probar dos «guardé 80 soles» el mismo día → marca «posible duplicado» →
      al confirmar, entra.
- [ ] **Pass:** ni falsos duplicados ni bloqueo del legítimo.

## Paso 5 — Congelar el número (marcador + fantasma SPY)

- [ ] Verificar a mano con 2 depósitos que el fantasma SPY cuadra (compra SPY en
      la fecha, retorno total, −$0.15).
- [ ] Si no cuadra a mano → no publicar; mostrar «sin dato» o etiqueta de
      estimación (respeta la regla aunque el resultado sea feo).
- [ ] **Pass:** un número decible en voz alta — «le gané/perdí al S&P por X» —
      o un «sin dato» honesto.

## Paso 6 — Sanity de la Alcancía con el costo real

- [ ] Recalcular N* con el F real; confirmar si la meta sigue en S/480
      (2×/año). Nota: el EOQ es robusto — con F entre ~$2.5 y $5 la cadencia
      no se mueve; solo un F muy alto (~$8+) la bajaría a 1×/año.
- [ ] **Pass:** cadencia coherente; si F real fuera muy alto, documentar el
      cambio a 1×/año.

## Paso 7 — Arrancar la rutina (lo que evita el abandono)

- [x] Registrar el primer «guardé 80 soles». *(ya hecho: progreso S/80)*
- [ ] Fijar el ancla: primer domingo de mes, 10 min.
- [ ] **Pass:** progreso de alcancía > 0 y recordatorio puesto.

## Definición de «Semana 0 terminada»

`depositado_neto = $949.41` ✓ · costos reales en CÁLCULO (o documentado por qué
siguen en ESTIMACIÓN) ✓ · marcador da un número (o «sin dato») ✓ · 0 duplicados
✓ · primer ahorro registrado ✓.

## Éxito de la Fase 1 (medir en semanas 2–4, no el $)

¿4 ahorros registrados? · ¿≥1 decisión de depósito con la Alcancía? ·
¿cuántas veces actuó el freno anti-impulso? · ¿sonó el aviso de «50 días sin
Hapi»?
