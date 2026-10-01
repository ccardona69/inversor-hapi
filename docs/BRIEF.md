# BRIEF — Fase 1: Marcador + Alcancía (spec congelada)

Una línea: la app mide la verdad (lo que salió del bolsillo vs. lo que vale hoy,
contra el S&P 500) y junta el ahorro en soles hasta el depósito eficiente.
Propone y registra; nunca opera en Hapi.

## Estado

Fase 1 implementada y verificada (26 sep 2026): 270/270 pruebas verdes, números
de aceptación cuadrados. **Congelada: los cambios se discuten antes de
codificar; la siguiente conversación es uso con datos reales, no rediseño.**

## Las 5 invariantes (no negociables)

1. **TC de mercado, jamás implícito.** El costo del depósito es
   `soles_enviados / tc_mercado_día − usd_llegado` (`costo_deposito`, scoreboard).
   El tc implícito de la fila (`fx_rate`) se guarda solo como dato: usarlo haría
   el costo 0 por construcción. `normalize_tc` acepta USD/PEN o PEN/USD
   (invierte <1) y descarta fuera de [2.5, 5]. Sin tc de mercado → `deposit_fee`
   ($3, ESTIMACIÓN) — nunca null ni "sin dato" en el costo.
2. **Los costos bajan el resultado.**
   `puesto_bolsillo = (depósitos − retiros) + costos_deposito`;
   `resultado_real = valor_actual − puesto_bolsillo`.
3. **El ahorro en soles no es depósito.** `depositado_neto` solo suma
   `deposito` − `retiro` en USD; `ahorro_soles` alimenta la alcancía aparte.
4. **Fingerprint detecta, no bloquea.** `kind|fecha|coalesce(amount_usd,
   soles_amount)`, sin `source`: lo mismo por captura y por texto choca; un
   duplicado legítimo confirmado por el usuario sí entra.
5. **Solo ~$3/depósito entra al marcador.** Las comisiones de operación ya vienen
   netas en los montos de Hapi; los dividendos ya están en `valor_actual`.

## Números de referencia (historial real)

- `depositado_neto = $949.41` (9 depósitos "Terminado"; excluidos $80 "Creado"
  y $20 "Expirado") · costos ~$27 ESTIMACIÓN · `puesto_bolsillo = $976.41`
  · `resultado_real = +$46.36 (+4.75 %)` con valor $1 022.77.
- Alcancía con S/80/mes y tc 3.55: `N* = 1.50` → `N_practico = ceil = 2`
  → meta práctica S/480 cada ~6 meses (óptimo exacto ~S/640).
- `progreso = max(0, Σ ahorro − Σ soles enviados)` — el sobrante queda.
- Fantasma SPY: retorno total (`adjclose`), compra el día del depósito o el
  hábil siguiente, −$0.15/compra; sin serie o sin precio posterior → "sin dato".
  Nota: dividendos sin retención del 30 % (~0.3 %/año).
- EOQ es robusto: con F real entre ~$2.5 y $5 la cadencia sigue en 2×/año;
  solo un F muy alto (~$8+) la bajaría a 1×/año.

## Reglas transversales

- Sin formularios: entrada por captura, texto pegado o conversación; borrador →
  confirmación siempre. Cada dato lleva HECHO/CÁLCULO/ESTIMACIÓN con fuente y
  fecha.
- El plan manda sobre el motor: en *Hoy*, motor/radar/DCF/niveles están plegados
  en «Avanzado» (no se borran).
- Luna: con el ETF bajo su meta (50 %), no recomienda comprar acciones
  individuales — respuesta determinista sin llamar al proveedor; insistir fuera
  de plan → «¿cambió la empresa o solo el precio?» → Diario.
- Solo 3 avisos: meta de alcancía · 50 días sin entrar a Hapi · W-8BEN ≤30 días.

## Reglas de ingestión (spec para futuros importadores — no implementadas)

Verificadas contra los 9 statements Apex (dic 2025 – ago 2026) el 27 sep 2026:

- **SEN como llave natural de depósitos.** Cada `JOURNAL from HAPI` trae
  referencia `SEN(...)` o `SEN...` (con y sin paréntesis, longitudes
  distintas): normalizar quitando paréntesis antes de deduplicar.
  Ejemplos reales: `SEN(20260415298174)` → $85.76 · `SEN20260824005013271`
  → $301.00.
- **Apex es fuente canónica de trades.** La app marca fecha de negociación
  (T) y monto redondeado; el statement marca liquidación (T+1) y monto
  exacto (diferencias de $0.01–0.02 por fracciones). Si se importan ambas
  fuentes: el canónico es Apex y el match es fuzzy (ticker + monto ±$0.05
  + fecha ±3 días); sin match → dos filas y discrepancia en el informe.
- **Ausencia como prueba, con condiciones.** Un depósito «Creado»/«Expirado»
  que no aparece como journal en el statement **completo** de su período
  (lag de acreditación observado ≤7 días) se prueba no-aterrizado —
  verificado: el $80 del 08 abr no existe en el statement de abril.
- **Bakkt/crypto nunca es depósito.** Los journals TIN/TOU de
  `BAKKT CRYPTO SOLUTIONS` son liquidación de operaciones cripto; solo
  `Journal from HAPI` alimenta `depositado_neto`.
- **PII:** los statements traen nombre, dirección y número de cuenta;
  anonimizar antes de usar como fixtures de test o exportarlos.
- **Zona horaria fija** America/Lima en todo parseo de fechas.

## Rutas Fase 1

`GET /api/marcador` (marcador + fantasma + alcancía + avisos) ·
`GET /api/alcancia` · `POST /api/flows/draft` · `POST /api/flows/confirm` ·
`GET/DELETE /api/flows/{id}`. Caché Yahoo 6 h (SPY + PEN=X).

## Backlog priorizado de Fase 2 (revisión 27 sep 2026)

En orden de impacto para el inversor:

1. **Costo de cambio visible y comparable.** El depósito ya calcula
   `soles/tc_mercado − usd_llegado`, pero `tc_ref` es el interbancario Yahoo —
   el costo medido incluye el margen de cualquier proveedor (la UI ya lo dice).
   Falta: (a) línea por depósito en soles con tc obtenido vs tc de referencia,
   (b) «fantasma de cambio» barato: campo opcional `mejor_tc_visto` en el
   borrador de depósito — el usuario anota la mejor tasa que vio (Rextie/
   Kambista) al cambiar y el delta se acumula en soles. Sin fuente nueva:
   el humano ya es parte del pipeline.
2. **F del EOQ descompuesta (a + b·Q).** El costo real del depósito parece
   mayormente proporcional (~2 %); el término proporcional no afecta la
   cadencia óptima (suma b·D fijo). Solo la parte fija `a` crea el trade-off.
   Con los 9 soles del BCP: ajustar `a` y `b`, recalibrar la cadencia —
   puede subir de 2 a ~4 depósitos/año si `a` es chica.
3. **Vigilante de estate tax.** Activos US-situs >$60 000 exponen a no
   residentes a impuesto sucesorio hasta 40 %; UCITS (CSPX/VUAA, domicilio
   Irlanda) lo evita y retiene 15 % a nivel fondo. Aviso dormido: dispara al
   acercarse al umbral. Dormido hoy (~$1 000) — que es el punto.
4. **VOO como fantasma** en vez de SPY (misma exposición, ER 0.03 % vs 0.095 %).
5. Tasa de ahorro como métrica principal del mes; radar/DCF tras puerta
   («se activa al 50 % de ETF»).
6. Deuda de modelo: forma canónica `(source, asof, verified)` en las tablas
   viejas; `fundamentals` append-only + `decisions` fijan `fundamentals.id`;
   `prices/manual` con sanity ±25 % y confirm; fantasma anclado al as-of de
   la cartera; canon `SEN` + fuzzy match para importador Apex.
7. Regla «2 de (soles, usd, fx_rate) determinan el tercero» — marcar cuál fue
   observado, derivar el resto.
8. Huella `UNIQUE` + contador de ocurrencia; `400`→`409` en confirm.

## El hueco que queda (revisión 27 sep 2026)

El sistema mide la palanca n.º 1 —cuántos soles entran— con precisión y
honestidad, pero **nada la mueve**: fantasma, guard, etiquetas y protocolo de
caída son medición y frenos. Ninguna función hace que entre un sol más, y el
aporte domina el resultado a 20 años. Puede que no pertenezca a este sistema;
queda escrito porque es el hueco que queda cuando todo lo demás está bien.

## Fuera de alcance (no reabrir sin conversación)

Fase 2 (metas 50/25/25, venta +15 % máx. 3, reparto por déficit) — gate
conductual: 4 semanas de rutina cumplida. Fase 3 (laboratorio en papel).
Descartados: Monte Carlo/bootstrap (candidatos revisión anual, como rango de
años históricos, sin probabilidades), XIRR (el fantasma ya es la comparación
justa), Kelly (ventaja demostrada = 0), CVaR (el panel de estrés basta con 2
acciones), escalera/DCA por niveles, predicciones, ejecución automática.
