# AUDITORÍA DE RIESGO — INVERSOR HAPI IA
## v1.1 «Ulises» — Página final consolidada

**Fecha:** 2026-10-01 · **Auditor:** externo · **Estado:** propuesta, nada implementado · **Autoridad:** `BRIEF.md` prevalece; si hay conflicto, gana el brief.

> **Alcance.** No tengo acceso al repositorio, base de datos, VPS ni Notion. No puedo crear páginas. Este es el contenido completo, listo para pegar donde corresponda. Las cifras externas (AWS, SUNAT, estate tax) van marcadas **HR — verificar vigencia** contra fuente oficial.

**Etiquetas:** HV = verificado por el agente · HR = reportado · INF = inferencia · REC = recomendación · CÁLC = cálculo derivado · EST = estimación con supuesto · **SIN DATO** = no verificable.

---

## 1. Veredicto

El motor determinista está bien pensado. El riesgo real está en la frontera entre el sistema y la realidad.

- **Circuito abierto.** La decisión real ocurre en Hapi. La regla vinculante vive en `trade_check`, endpoint API-only que la SPA nunca invoca. El sistema no ve el antes ni el después. **(INF/HR)**
- **Ulises sin cuerdas.** Quien está constreñido por la regla puede editarla sin fricción ni rastro inmutable. **(INF)**
- **Inversión de materialidad.** A este tamaño y tasa de ahorro, el crecimiento del próximo año viene mayormente de aportes, no de retorno. **CÁLC (EST, r=0.05):** retorno esperado ≈ $50.6/año; aportes declarados ≈ $270/año. La mayoría de los módulos sirven a *elegir*, que es justo lo que la regla prohíbe por ~4 años.
- **Base no reproducible.** Producción ≠ documentación. Working tree sucio. Dos bases. Backups en el mismo disco. Sin restore probado.
- **Medición blanda.** Estimaciones presentadas como hechos. Verificación sin evidencia. Hueco fail-closed en el denominador de `etf_pct`.

**Veredicto provisional:** el sistema puede fallar más por **circuito abierto, autoengaño metodológico y complejidad frágil** que por una mala decisión de inversión aislada.

---

## 2. Orden de lectura (principio de diseño)

El output del sistema debe leerse siempre en este orden:

1. **El plan** — regla, meta, estado actual, brecha.
2. **El motor** — cálculo determinista, sin IA.
3. **La decisión preliminar del usuario** — lo ya expresado o registrado.
4. **Luna (IA)** — contraargumentos, nunca como primera lectura.

Luna no abre la conversación. Cierra, cuestiona, advierte. No decide.

---

## 3. Marco único de pérdida

Un solo marco, coherente, sin contradicciones internas.

- **El perfil manda.** El umbral de pérdida tolerable del perfil es el marco principal.
- **Stops ATR = tácticos.** Rotulados como herramienta táctica. **No aplican al plan.**
- **Estrés uniforme −50% = ilustrativo.** Etiquetado como “no distingue composición”. **CÁLC:** es identidad algebraica salvo por cash.
- **HHI cuenta el ETF como una sola unidad.** Documentado. **CÁLC:** 100% SPY daría HHI = 1.0 (máxima “concentración”), absurdo. Actual ≈ 0.505 (N_eff ≈ 1.98); con SPY al 50% ⇒ 0.376 (N_eff ≈ 2.66).

---

## 4. Paquetes de trabajo v1.1 «Ulises»

**Principios:** no agregar features de selección ni timing · cerrar el circuito · todo medible y fechado · **v1.1 no cambia esquema** · el sistema nunca elige la ruta por el usuario.

**Gobernanza:** Fase 1 congelada. Nada se implementa sin discusión previa, aprobación explícita, commit limpio, tests verdes en HEAD, backup verificado y plan de reversión.

---

### P0 — G0: suelo reproducible

| ID | Acción | Aceptación |
|---|---|---|
| P0.1 | Commitear working tree o descartarlo conscientemente. | Commit inmutable. |
| P0.2 | Tag del commit desplegado. | Tag creado. |
| P0.3 | Diff contra `37fc4bc`. | Informe de diferencias. |
| P0.4 | Correr 311 tests en HEAD limpio. **(HR: 311 verdes; confirmar si son sobre contenido aplicado no commiteado.)** | Verdes en HEAD. |
| P0.5 | Declarar VPS como base canónica; congelar local. | Documentado y aplicado. |
| P0.6 | Backup `VACUUM INTO` + copia off-site cifrada. | Backup off-site verificado. |
| P0.7 | Prueba de restauración documentada. | Restore exitoso, integridad verificada. |
| P0.8 | `delete_all` con backup previo automático y confirmación tipada. | No ejecutable con un clic. |
| P0.9 | Mostrar hash del commit desplegado en UI/API. | Visible y contrastable. |

**Cambios pendientes a consolidar en un commit con tag:** lista ETF_META · numerador de `etf_pct` solo verificado · `dinero_nuevo` y `evaluable` en `/api/brecha` · validación de `PUT /api/plan` contra ETF_META.

---

### P1 — Cerrar el circuito

| ID | Acción | Aceptación |
|---|---|---|
| P1.1 | Pantalla de preflight: ticker, lado, monto, `trade_check`, registro de decisión. | Consultable antes de operar en Hapi. |
| P1.2 | Exponer `trade_check` en UI. | SPA lo invoca. |
| P1.3 | Verificar que `POST /api/analysis/{t}` consulte la regla del plan. | Sin recomendaciones de compra individual sin banner. |
| P1.4 | Banner de plan en toda mención de ticker no-ETF. | Consistente en radar, niveles, análisis, chat. |
| P1.5 | Detector de desviaciones: último snapshot en `settings`, comparación contra nuevo. | Desviación = acción sin decisión registrada. |
| P1.6 | Rutina semanal &lt;5 min: `ahorro_soles`, mirar plan, registrar trade. | Registro semanal observable. |
| P1.7 | Cierre de mes: foto de posiciones Hapi + verificación con evidencia. | Evidencia fechada en `source`. |

---

### P2 — Silenciar lo inmaterial

| ID | Acción | Aceptación |
|---|---|---|
| P2.1 | Modo estudio: radar, ATR, pulso, DCF ocultos/no accionables mientras `etf_pct &lt; target`. | Sin señales accionables de compra individual. |
| P2.2 | Congelar refresh de radar/pulso sin decisión pendiente. | Sin fetches innecesarios. |
| P2.3 | Umbral de materialidad para nuevas features (propuesta: &gt; $5k o `etf_pct ≥ 50%`). | Justificación obligatoria. |
| P2.4 | Etiquetar estrés uniforme como “ilustrativo, no distingue concentración”. | Visible. |
| P2.5 | Documentar contradicción AMZN 27.5% vs. límite 25% en estado final. **(CÁLC: $2,024 total, AMZN 27.5%, GOOG 22.5%, ETF 50%.)** | Visible. |
| P2.6 | HHI con tratamiento especial de ETF_META. | No wrong-signed. |
| P2.7 | Revisar coherencia ATR stops vs. pérdida tolerable del perfil. | Sin contradicción interna. |

---

### P3 — Fail-closed

| ID | Acción | Aceptación |
|---|---|---|
| P3.1 | **Denominador conservador.** Posiciones sin precio fuera de ETF_META ⇒ `evaluable:false` con razón. | Regla no evaluable si falta dato. |
| P3.2 | **Caducidad de precios** según antigüedad del dato (propuesta: N=5 días hábiles). | “Sin dato” si vencido. |
| P3.3 | **Propagación de etiqueta más débil.** Input EST ⇒ output EST. Un marcador con costos estimados queda rotulado como ESTIMACIÓN. | Auditoría de etiquetas. |
| P3.4 | `verify_all` requiere evidencia por ítem o muestra cuáles faltan. | No es sello de goma. |
| P3.5 | `soles_amount` blando obligatorio hacia adelante. | Costo real medido. |
| P3.6 | **Pruebas de invariantes aleatorizadas**, sin dependencias nuevas. Verifican que agregar posiciones sin precio nunca vuelve más permisiva la regla. | Habría atrapado el bug del denominador. |

---

### P4 — Fuentes, operación y guardas IA

| ID | Acción | Aceptación |
|---|---|---|
| P4.1 | **Canario diario** de fuentes (precio, tipo de cambio, SEC, IA). Tests semanales marcados en rojo en el VPS. | Estado de fuentes visible. |
| P4.2 | Red-team semanal de guardas IA. | Reporte de evasiones. |
| P4.3 | **Filtro de afirmaciones prohibidas** (catalizadores futuros, noticias inventadas, predicciones). | Post-guard determinista. |
| P4.4 | Golden fixtures de respuestas reales. | Regresión de guardas. |
| P4.5 | **Tope de gasto** de proveedor IA. | Límite configurado. |
| P4.6 | **Registro de datos de salida** al proveedor IA. | Documentado. |
| P4.7 | **Seguridad:** enlace mágico de un solo uso con expiración, cookies seguras, revocación, `uvicorn` restringido a localhost, secretos fuera de git, acceso de emergencia sin abrir el puerto 22, parches del sistema. | Checklist fechado firmado. |
| P4.8 | Backups cifrados antes de salir del VPS. | Verificado. |
| P4.9 | Avisos de ingesta: duplicados difusos, estados distintos de “Terminado”. | No bloquean, avisan. |

---

### P5 — Verdad económica

| ID | Acción | Aceptación |
|---|---|---|
| P5.1 | **Costo real de la herramienta** como hecho verificable con factura. | Visible en panel. |
| P5.2 | Comparación contra estimación de retorno sobre cartera. | Visible. |
| P5.3 | **KPI: cobertura de costo real en depósitos.** | Medido. |
| P5.4 | Declaración **“impuesto en Perú: sin dato”** en proyecciones de rebalanceo. | Visible. |
| P5.5 | Tareas fuera del software: confirmar tarifas reales, documentar ajuste práctico del EOQ. | Documentado. |
| P5.6 | **Criterio de corte:** si costo anual ≥ retorno esperado (~$50.6/año a r=0.05 sobre ~$1,012), degradar infraestructura o apagar módulos no esenciales. | Decisión registrada. |

**CÁLC de referencia:** infra $5–15/mes = $60–180/año = 6–18% del portafolio. Comisión fija $3 sobre aporte $135 ⇒ 2.22%. Sobre promedio $105 ⇒ 2.86%. 8 aportes × $3 = $24 de drag fijo. **HR — verificar:** AWS IPv4 ~$0.005/hora ⇒ ≈ $43.80/año (≈ 87% del retorno esperado). **EOQ:** S=3, D≈270, H=0.05 ⇒ ≈ 180 unidades.

**Resistencia de la cartera (CÁLC, EST con tc≈3.55 y r=0.05):**
- Ahorro declarado S/80/mes ≈ $22.5/mes ⇒ ≈ $270/año ⇒ ~5.0 años para duplicar la cartera.
- Ahorro S/160/mes ≈ $45/mes ⇒ ≈ $540/año ⇒ ~2.5 años para duplicar la cartera.

---

### P6 — Gobernanza del plan

| ID | Acción | Aceptación |
|---|---|---|
| P6.1 | `pending_changes` en settings para `etf_target_pct` y límites. | Estado pendiente visible y cancelable. |
| P6.2 | Enfriamiento (propuesta: 72h o 7 días). | No aplicable de inmediato. |
| P6.3 | Confirmación tipada y registro con motivo. | Journaled. |
| P6.4 | Usuario debe elegir y fechar una de las tres rutas (ir lento, ahorrar más, rebalancear). | Decisión explícita y registrada. |
| P6.5 | **Redefinición del gate conductual** (propuesta de cambio de spec). Ver §5. | Auditable sin bitácora nueva. |
| P6.6 | Bitácora append-only a Fase 2, prioridad 1. | Backlog explícito. |

---

## 5. Gate conductual (propuesta de cambio de spec)

**Problema:** “4 semanas de rutina cumplida” no mapea a una cadencia real de ~6 meses entre depósitos. En cualquier ventana de 4 semanas probablemente no hay depósitos ni trades. El gate mide nada.

**Propuesta:** rutina semanal de 5 minutos.

- Registrar el ahorro semanal (`ahorro_soles`).
- Verificar si se operó en Hapi.
- Si hubo operación, registrar decisión.

**Gate a Fase 2:**

- P0 completo.
- **4 semanas consecutivas** con al menos un registro `ahorro_soles` y cero desvíos no documentados.
- Usa tablas existentes. Sin nuevo esquema.

**Objetivo:** que el ahorro pase de ser **declarado** a ser **medido**. Hoy hay solo 1 registro `ahorro_soles` contra un objetivo declarado de S/80/mes. La rutina no está corriendo.

**Limitación:** `ahorro_soles` puede editarse. No es tamper-proof. La bitácora append-only va a Fase 2.

---

## 6. Criterios de éxito y corte (revisión a 8 semanas)

### Éxito

- G0 completo con restauración probada.
- 100% de depósitos nuevos con costo real.
- Rutina sostenida: ≥4 semanas consecutivas con registro.
- 0 desvíos sin registrar.
- Costo de la herramienta visible con factura.
- Gate Fase 2 auditable con datos existentes.

### Corte

- **Si no hay rutina establecida a las 8 semanas:** congelar el desarrollo y reducir el sistema a lo mínimo — **ficha del plan, alcancía y marcador**. Más código no arregla una falla de comportamiento.
- **Si el costo anual de la herramienta supera el retorno esperado (~$50.6/año):** evaluar bajar la infraestructura o apagar módulos no esenciales.
- **Radar:** si tras refresh completo sigue con &lt;10% de cobertura de fundamentales (**CÁLC: 2/78 = 2.6%; faltan_datos 76/78 = 97.4%**), congelarlo hasta Fase 2.

---

## 7. Fuera de alcance de v1.1

- Nuevas fuentes de datos.
- Ampliación del radar.
- Nuevas funciones de IA.
- Cambios de esquema.
- Integración con Hapi.
- Proyecciones de precio.
- Selección o timing.

---

## 8. Backlog Fase 2 (condicionado a pasar el gate)

1. **Bitácora append-only de decisiones y aportes** — prioridad 1. Todo lo demás depende de esto.
2. Vínculo decisión–operación.
3. Medición de cumplimiento hacia adelante.
4. Estrés por activo con drawdown histórico y ventana declarada.
5. Look-through del ETF en HHI.
6. Reconciliación con estado de cuenta Hapi.
7. Módulo fiscal verificado con contador.
8. Rediseño de radar/pulso subordinado al plan.
9. Autenticación más robusta que magic link.
10. Reconstrucción histórica de costos con `soles_amount` y TC de mercado.
11. Migración a UCITS si el portafolio se acerca a $60k. **(HR — verificar umbral.)**
12. Presupuesto de complejidad y revisión trimestral.

---

## 9. Verificaciones solicitadas al agente (VAs)

Pasar esta tabla al agente. Pedir respuesta con **archivo y línea**.

| ID | Verificación |
|---|---|
| VA-1 | ¿`decisions.py` y el endpoint de análisis consultan la regla del plan? `file:line`. |
| VA-2 | ¿Qué endpoints modifican `etf_target_pct` u otros parámetros del plan? `file:line`. |
| VA-3 | ¿Cómo se maneja `etf_pct` sin precio? ¿Excluye del denominador? `file:line`. |
| VA-4 | ¿Se rechazan precios antiguos? ¿Hay TTL de staleness? `file:line`. |
| VA-5 | ¿El marcador etiqueta estimaciones cuando el costo es EST? `file:line`. |
| VA-6 | ¿El fantasma SPY replica costos y fechas del marcador real? `file:line`. |
| VA-7 | ¿`plan_guard` cómo detecta intención? ¿Hay tests de evasión? `file:line`. |
| VA-8 | ¿Enlace mágico: entropía, expiración, un solo uso, flags de cookie, revocación? `file:line`. |
| VA-9 | ¿Estado de los backups: dónde, cuándo, restore probado? `file:line`. |
| VA-10 | ¿Base del snapshot §7: VPS o local? ¿Timestamp? `file:line`. |
| VA-11 | ¿`delete_all`: backup previo, confirmación, Origin check? `file:line`. |
| VA-12 | ¿Rango histórico solicitado a Yahoo en `marketdata.py`? `file:line`. |
| VA-13 | ¿La comisión de depósito $3 es por transacción, en USD, siempre? `file:line`. |
| VA-14 | ¿Qué contexto exacto se envía al proveedor IA? `file:line`. |
| VA-15 | ¿`etf_pct` usa precio×cantidad o valor de Hapi? `file:line`. |
| VA-16 | ¿El check de “operación ≤10% del total” aplica a compras de ETF_META? El aporte del plan lo excedería. `file:line`. |

---

## 10. Cómo usar este documento

1. Pasar la tabla VAs al agente. Pedir respuestas con archivo y línea.
2. Con esas respuestas, **aprobar o rechazar cada paquete** (P0–P6).
3. Ejecutar **G0 completo** antes de escribir cualquier línea de código.
4. Nada se implementa sin aprobación explícita.
5. Registrar cada decisión en `DECISIONES.md`.

---

## 11. Nota final

El sistema tiene una intención sólida: medir la verdad y frenar decisiones impulsivas. Pero hoy el riesgo principal es que **la herramienta sea más compleja, cara y frágil que el problema que resuelve**, y que su regla vinculante viva en un endpoint que nadie llama.

v1.1 «Ulises» no agrega features de selección ni timing. Cierra el circuito, silencia lo inmaterial, cierra huecos fail-closed, ordena fuentes y operación, mide el costo de la herramienta y pone fricción a los cambios de plan.

No elijo por ti entre ir lento, ahorrar más o rebalancear. El sistema debe presentarte escenarios comparables y permitirte decidir con fricción y registro.

**Próximo paso:** pasar la tabla VA al agente del proyecto, aprobar o rechazar cada paquete antes de escribir código.

---

*Documento de trabajo. No es una página de Notion ni un commit. Es una propuesta sujeta a aprobación explícita.*

---

## Anexo — Estado de respuesta (2026-10-02, agente del proyecto)

Las VA-01 a VA-16 fueron respondidas con `file:line` en `AGENTS.md` §7 y en
`VERIFICACIONES.md`. Correcciones relevantes a las premisas de esta auditoría:

- **VA-02:** `etf_target_pct` no tiene escritor por API. Los editables sin
  fricción ni rastro son `PUT /api/limits` y `PUT /api/profile`.
- **VA-03:** el denominador de `etf_pct` ya era conservador (solo posiciones con
  valor). El hueco real era el numerador (ETF sin verificar contaba) — corregido
  con `ETF_META` + `verified`.
- **VA-04:** sí existe TTL de staleness (≤24 h actual, ≤5 d reciente).
- **VA-16:** confirmado y corregido — las compras de ETF_META quedan exentas del
  límite «máximo por operación».
