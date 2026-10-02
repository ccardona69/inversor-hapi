# AGENTS.md — Inversor Hapi IA

Versión: 1.0 — 2026-10-01 (Lima)
Verificado contra: commit desplegado 2026-10-02 (tag en git; hash consultable
con `git rev-parse HEAD` en el VPS) — incluye ETF_META, numerador
solo-verificado, dinero_nuevo/evaluable, PUT /api/plan contra ETF_META y la
corrección VA-16.
Propósito: instrucciones vinculantes para cualquier agente de IA que opere sobre
el repositorio, la base de datos o el VPS de Inversor Hapi IA.
Idioma: español.
Alcance: prevalece sobre CLAUDE.md, briefs y convenciones previas, salvo
docs/BRIEF.md (spec congelada), que prevalece sobre todo. CLAUDE.md sigue siendo
la guía técnica (stack, comandos, módulos); este archivo es el gobierno.

---

## 0. Identidad

Inversor Hapi IA es un sistema mono-usuario de soporte a la decisión para el
bróker Hapi. No ejecuta órdenes, no predice precios, no elige por el usuario.
Mide la verdad, presenta escenarios comparables y registra decisiones.

- Bróker: Hapi. Sin API pública; toda operación es manual en su app.
- Cuenta: de efectivo, sin margen ni apalancamiento (HR — verificar en Hapi).
- Infraestructura: AWS EC2 ARM64, systemd, Caddy HTTPS, cookie-gate por enlace
  de entrada; uvicorn solo en loopback (run_local.py:12).
- Base de datos: SQLite (WAL). Canónica: la del VPS. La local es copia de
  desarrollo y no se usa como fuente de verdad.
- Proveedor de IA: externo, vía app/ai_provider.py únicamente. Recibe contexto
  financiero del usuario (ver VA-14).
- Fases: Fase 1 congelada. Fase 2 exige gate conductual (§15). v1.1 «Ulises»
  es propuesta pendiente de aprobación por paquete.
- Metáfora rectora: Ulises atado al mástil. Radar y pulso son las sirenas; el
  plan es el mástil; enfriamiento y evidencia son las cuerdas; el modo
  hibernación es la cera.

---

## 1. Reglas duras

1. No ejecutar órdenes. El sistema sugiere, registra y advierte.
2. No proyectar precios: sin precio objetivo, sin «va a subir/bajar». Un
   escenario histórico rotulado como tal (§5.3) no es proyección.
3. No inventar catalizadores, noticias ni eventos. Sin fuente fechada, no existe.
4. No usar lenguaje de venta («oportunidad», «imperdible», «hay que comprar»).
5. Luna opina, el motor decide, el usuario autoriza. Ninguna salida del modelo
   es veredicto.
6. No elegir la ruta por el usuario: ir lento, ahorrar más o rebalancear se
   presentan como escenarios comparables. El usuario elige, fecha y registra.
7. No tocar código sin verificación file:line previa.
8. No cambiar esquema en v1.1. Todo cambio de esquema va a Fase 2 (G2).
9. No implementar sin aprobación explícita del usuario.
10. No exponer secretos, IPs, dominios, rutas de entrada, cookies ni datos
    financieros identificables en respuestas, logs, commits o documentación.
11. La hibernación colapsa, nunca borra.
12. Todo resultado hereda la etiqueta más débil de sus insumos.
13. Los datos del usuario nunca dependen de un único lugar físico ni de una
    única cuenta de proveedor.
14. No importar marcos de trading activo (§8). El sistema no opera; sus riesgos
    son de concentración, conducta, fricción y pérdida de datos.

---

## 2. Taxonomía epistemológica

| Etiqueta | Significado |
|---|---|
| HV | Hecho verificado por el agente, con file:line o evidencia reproducible. |
| HR | Hecho reportado por el usuario o fuente externa. Requiere verificación y fecha. |
| INF | Inferencia del agente, declarada como tal. |
| REC | Recomendación. Todo v1.1 es REC por definición. |
| CÁLC | Cálculo sobre cifras HV o HR. |
| EST | Estimación con supuesto explícito. |
| SIN DATO | No verificable con lo disponible. Se declara, no se rellena. |

Propagación: un CÁLC sobre un HR se reporta como CÁLC (HR); sobre un EST, como
EST. Materialidad: todo número lleva fuente y fecha; sin fuente, es SIN DATO.

---

## 3. Compuertas

### G0 — suelo reproducible (antes de cualquier cambio)
- Working tree limpio o descartado conscientemente.
- Commit desplegado = tag = HEAD; hash visible en API o UI.
- Tests verdes sobre HEAD limpio (no sobre el working tree).
- Backup off-site cifrado, con restauración probada y fechada.
- delete_all precedido de backup automático.

### GC — cambios dentro de Fase 1 (sin esquema)
Aprobación explícita · file:line previo · aceptación medible · reversión
documentada.

### G2 — Fase 2
Gate conductual cumplido y auditable · backlog priorizado y aprobado ·
backup + migración reversible ensayada en copia.

---

## 4. Estado actual (snapshot 2026-10-01, base canónica VPS — se degrada)

| Concepto | Valor | Etiqueta |
|---|---|---|
| Valor de posiciones | ≈ USD 1,012 | HV (/api/brecha en VPS) |
| Composición | AMZN ≈ 55 %, GOOG ≈ 45 %, ETF 0 % vs meta 50 % | HV |
| Grupo correlacionado | 100 % en «tecnología / IA» (app/risk.py:13-16) | CÁLC |
| HHI / N efectivo | ≈ 0.505 / ≈ 1.98 | CÁLC |
| Límites propios incumplidos hoy | AMZN 55 % > 25 % por posición; > 40 % por sector | CÁLC |
| Depósitos | 9 «Terminado», ≈ USD 949 netos, 0/9 con soles_amount | HV |
| Ahorro registrado | 1 registro ahorro_soles vs S/80/mes declarado | HV |
| Venta para rebalancear hoy | ≈ USD 506 | CÁLC |
| Dinero nuevo para llegar a la meta sin vender | ≈ USD 1,012 | CÁLC |
| Aportes necesarios a ≈ USD 135 c/u | ≈ 8 (≈ 4 años a cadencia ≈ 6 meses) | EST (precios constantes) |
| Retorno esperado | ≈ USD 50.6/año (r = 0.05) | EST |
| Aportes declarados | ≈ USD 270/año (S/80/mes a tc ≈ 3.55) | EST |
| Comisión de transferencia BCP → Hapi | USD 2.99 por depósito (4/4 coincidencias: 21 may, 24 ago, 25 ago, 8 sep 2026) ≈ 2.21 % de un aporte de USD 135 | CÁLC (HR estado de cuenta BCP) |
| Spread de «Yape Compra USD» | 24 ago: S/1,028 → USD 296.30, tc pagado 3.4695 vs mercado 3.3515 ≈ +3.5 % ≈ USD 10.4 de costo adicional (si el cargo cubre también los 8.28: tc 3.3751 ≈ +0.7 %). Único punto medible: los soles salieron de Interbank y esa cuenta fue eliminada — el spread histórico es SIN DATO irrecuperable | CÁLC (HR estados BCP; mercado: Yahoo PEN=X) |
| Costo real por depósito | ≈ USD 2.99 de tarifa + spread de cambio. Si el spread es ≈ 3.5 % (única observación), un aporte de USD 135 cuesta ≈ USD 7.7 (≈ 5.7 %), no USD 3 (≈ 2.2 %). Historia: EST para siempre; hacia adelante se mide con soles_amount | EST (una observación) |
| Transferencias sin depósito registrado | 26 may 11.79 · 3 jun 10.03 · 17 jun 18.09 = 39.91; cada una se financió con compras Yape del mismo día; abono «KALLPA» 39.95 el 24 ago. Hipótesis: depósitos devueltos (INF). Si no lo fueran, faltarían ≈ USD 31 en depósitos | INF — verificar detalle del abono o historial Hapi |
| Radar | 2/78 con fundamentales (2.6 %) | HV/CÁLC |
| Tests | 312 verdes en HEAD desplegado | HV |

### Deuda técnica (corregida contra el código)
- Backups: rotación en el disco del VPS + copia off-site cifrada (AES-256)
  en PC local desde 2026-10-02; integridad verificada tras descifrar.
- trade_check, /api/brecha y PUT /api/plan son API-only: static/app.js no los
  invoca.
- POST /api/analysis/{t} no consulta la regla del plan (decisions.py:55-142).
- PUT /api/limits (decisions.py:393-397) y PUT /api/profile (profile.py:17-22)
  aceptan cualquier valor, sin validación, enfriamiento ni rastro. Este es el
  hueco «Ulises» real. etf_target_pct no tiene escritor por API.
- Fallback a hapi_value de captura sin límite de antigüedad (portfolio.py:56-60).
- resultado_real del marcador sin etiqueta propia (scoreboard.py:127,135).
- verify_all marca todo verificado en un UPDATE, sin evidencia (portfolio.py:262-266).
- plan_guard por palabras clave (ai_assistant.py:41-44); sin pruebas de evasión.
- Proveedor IA sin tope de gasto ni política de datos declarada
  (ai_provider.py:164 max_tokens 2048; :202 timeout 120 s).
- Enlace de entrada estático y cookie de 1 año, sin un solo uso (VA-08).
- Yahoo Finance (no oficial) como fuente única de precio y tipo de cambio.
- .secrets/ai.env en texto plano en el disco del VPS.

---

## 5. Riesgo de ruina operativo

### 5.1 Pérdida de datos por la cuenta AWS (prioridad máxima)
- La cuenta está en Free plan (HR, usuario, 2026-10-01). Un Free plan expira a
  los 6 meses de abierta o al agotar créditos, lo que ocurra primero; luego se
  pierde el acceso y a los 90 días se borran recursos y datos, salvo que se
  pase a Paid plan (HR — AWS Free Tier docs y términos, consultados
  2026-10-01).
- Créditos reportados: USD 120 (HR, usuario). Apertura de la cuenta: ≈
  2026-10-01 (HR, usuario). Vencimiento del Free plan: ≈ 2027-04-01 o al
  agotar créditos (≈ 2027-05), lo que ocurra primero — la fecha dura es
  ≈ 2027-04-01 (CÁLC sobre HR).
- Costo estimado t4g.small: USD 0.0168/h ≈ 12.26/mes + IPv4 pública
  USD 0.005/h ≈ 3.65/mes + EBS 8 GB gp3 ≈ 0.64/mes ≈ USD 16.55/mes ≈ 199/año
  (EST; precios HR on-demand, región y tamaño de disco supuestos).
- Créditos / costo ≈ 7.3 meses (EST): el límite de 6 meses llega antes.
- Mitigación previa a cualquier código: backup off-site fuera de AWS y decisión
  registrada sobre el plan de cuenta.

### 5.2 Costo de la herramienta frente al criterio de corte
Escenarios comparables (EST, sin elegir):

| Escenario | Costo anual | vs ≈ USD 50.6 |
|---|---|---|
| A. Paid + t4g.small + límite de gasto | ≈ USD 199 | ≈ 3.9× |
| B. Paid + t4g.micro (1 GB + swap) | ≈ USD 125 | ≈ 2.5× |
| C. Solo local + túnel | ≈ USD 0 infra (PC encendida) | pasa |
| D. Mantener y registrar la desviación con motivo | según A/B | excepción consciente |

INF: el criterio compara contra el retorno, pero el valor buscado es conductual
(evitar concentración e impulsos). Ese valor es SIN DATO; por eso la desviación,
si se elige, se registra en DECISIONES.md, no se ignora.

### 5.3 Escenario de mercado (ilustrativo, no proyección)
Réplica de caídas máximas de 2022, no simultáneas: AMZN ≈ −56 %, GOOG ≈ −45 %,
SPY ≈ −25 % (HR — verificar con serie histórica).

| Cartera | Caída | Etiqueta |
|---|---|---|
| Actual (55/45) | ≈ −51 % ≈ −USD 517 | CÁLC (HR) |
| Estado final del plan (50 % ETF / 27.5 % / 22.5 %) | ≈ −38 % | CÁLC (HR) |
| Pérdida tolerable por defecto | 30 % (app/risk.py:5) | HV |

Ambas superan el umbral por defecto. El perfil real del usuario puede tener otro
valor (SIN DATO). Revisar meta o tolerancia es decisión del usuario.

### 5.4 Ruina conductual
Mecanismo: abandonar el plan tras una caída, o editar límites para justificar una
compra. Mitigación: P1 (circuito), P6 (fricción) y el gate de §15.

---

## 6. Protocolo de verificación (siete pasos)
1. Citar file:line. 2. Describir comportamiento actual con evidencia.
3. Declarar SIN DATO. 4. Etiquetar todo. 5. Proponer solo con aprobación.
6. Definir aceptación medible. 7. Documentar reversión.
Sin estos pasos, la propuesta no es válida.

---

## 7. Verificaciones VA-01 a VA-16 (respondidas 2026-10-01)

| ID | Respuesta | Evidencia | Estado |
|---|---|---|---|
| VA-01 | analysis/{t} no consulta regla_plan; chat y trade_check sí | decisions.py:55-142; ai_assistant.py:74; decisions.py:274 | Gap → P1.3 |
| VA-02 | etf_target_pct sin escritor; limits y profile sin validación ni rastro | decisions.py:393-397; profile.py:17-22 | Gap → P6 |
| VA-03 | Excluye solo sin precio y sin hapi_value; trade_check bloquea con 400 | portfolio.py:53-62; decisions.py:72-75 | Parcial → P3.1 |
| VA-04 | TTL: ≤ 24 h actual, ≤ 5 d reciente, > 5 d no usable; fallback de captura sin TTL | marketdata.py:75-95; portfolio.py:56-60 | Parcial → P3.2 |
| VA-05 | Costos etiquetados; resultado_real no | scoreboard.py:121,132,127,135 | Parcial → P3.3 |
| VA-06 | Fantasma: USD 0.15 fijo por compra simulada, retención 30 %; no replica costo real de depósito | scoreboard.py:138 | Documentar |
| VA-07 | Regex de verbos + tokens [A-Z]{1,5}; evadible («me animo con NVDA», minúsculas); sin tests de evasión | ai_assistant.py:41-44,73 | Gap → P4.2 |
| VA-08 | Ruta de entrada estática, cookie 1 año HttpOnly/Secure/SameSite=Lax, sin un solo uso; revocar = editar Caddy | Caddyfile desplegado; run_local.py:12 | Media → P4.7 |
| VA-09 | VACUUM INTO a backups/ (rotación 10) + copia off-site cifrada (AES-256) en PC desde 2026-10-02; integrity_check OK tras descifrar; clave entregada al usuario | db.py:132-157; system.py:22-28 | Resuelto |
| VA-10 | Snapshot §4 tomado del VPS | /api/brecha en VPS, 2026-10-02 00:20 UTC | Resuelto |
| VA-11 | Confirmación «ELIMINAR» + Origin/Referer por middleware + backup automático previo desde 2026-10-02 | system.py:63-72; main.py | Resuelto |
| VA-12 | Histórico 1y por defecto; fantasma 5y; cotización 5d | marketdata.py:31,47; marcador.py:39 | Resuelto |
| VA-13 | deposit_fee USD 3 fijo por depósito, solo como ESTIMACIÓN; meta S/480 por EOQ | scoreboard.py:16,99-101; alcancia.py:15-16,61-62 | Resuelto |
| VA-14 | Hasta 40 posiciones, 20 fundamentales, 5 tesis, 10 propuestas, 15 alertas, pulso, plan, límites, perfil; sin política ni tope | ai_assistant.py:149-208; ai_provider.py:164,202 | Gap → P4.5-6 |
| VA-15 | qty × precio usable; si no, hapi_value rotulado «verificar»; inconsistencias en /api/validate | portfolio.py:54-57,309 | Resuelto |
| VA-16 | Máximo por operación 10 % aplicaba a ETF_META y el aporte del plan (≈ 13.3 %) salía «no cumple». Corregido 2026-10-01: las compras de ETF_META quedan exentas; las ventas de ETF siguen limitadas | decisions.py:295-303; test_trade_check.py (test_aporte_del_plan_no_choca_con_maximo_por_operacion) | Corregido, sin commit |

---

## 8. Marcos externos: qué aplica y qué no

No aplican (introducirían timing, prohibido por las anti-metas):
riesgo por trade de 1-2 %, stops por operación sobre el plan, filtros FOMC/CPI/
earnings, drawdown diario, protocolos de latencia, Sharpe de producción.
Sharpe: SIN DATO; el sistema no genera serie de retornos propia.

Sí aplican, traducidos:
- Dimensionamiento → límites de concentración y grupo correlacionado.
- Riesgo de ruina → pérdida de datos (§5.1), costo > retorno (§5.2),
  abandono conductual (§5.4). Sin apalancamiento no hay liquidación por mercado.
- Fricciones → comisión de depósito, spread de tipo de cambio (≈ 0.2 %, HR),
  spread de Hapi (SIN DATO), retención 30 % sobre dividendos (HR).
- Mismo escenario a cartera actual y futura (§5.3).

---

## 9. Comportamientos prohibidos
Los de §1, y además: probabilidades sin sustento; estimaciones presentadas como
hechos; omitir la etiqueta más débil; cifras sin fuente y fecha; borrar datos al
hibernar; proponer features de selección o timing en v1.1.

---

## 10. Lenguaje
Español sobrio. USD en vez de $. ≈ y ≤ en vez de ~ y <=. Comillas «». Sin emojis.
Negrita solo estructural. Declarar SIN DATO en vez de rellenar. El usuario es el
principal, no un cliente.

---

## 11. Archivos de gobierno

| Archivo | Propósito | Estado |
|---|---|---|
| AGENTS.md | Este archivo | creado |
| docs/BRIEF.md | Spec congelada, autoridad superior | existe |
| docs/PLANOS_DE_LA_CASA.md | Blueprint (renombrado desde BRIEF-PARA-IA.md) | creado |
| docs/AUDITORIA_v1.1_ULISES.md | Auditoría y paquetes | creado |
| docs/VERIFICACIONES.md | Historial de VA | creado |
| docs/DECISIONES.md | Registro de decisiones del usuario | creado |
| docs/BACKLOG_FASE2.md | Backlog Fase 2 | creado |

Crear los faltantes con la misma disciplina de etiquetas, previa aprobación.

---

## 12. Flujo con el usuario
Plantea → el agente verifica file:line → etiqueta → propone escenarios sin
elegir → el usuario aprueba, rechaza o ajusta → el agente implementa solo con
aprobación → documenta aceptación y reversión en DECISIONES.md.

---

## 13. Éxito y corte (revisión a 8 semanas)
Éxito: G0 completo con restore probado · 100 % de depósitos nuevos con costo
real · ≥ 4 semanas consecutivas con registro · 0 desvíos sin registrar · costo
de la herramienta visible con factura · próximo aporte según el plan o excepción
registrada.

Corte:
- Rutina: si no está establecida a las 8 semanas, se congela el desarrollo y el
  sistema queda en ficha del plan, alcancía y marcador.
- Costo: si costo anual ≥ retorno esperado, se elige un escenario de §5.2 y se
  registra.
- Radar: si tras refresh completo la cobertura sigue < 10 %, se congela hasta
  Fase 2.

Anti-metas v1.1: sin nuevas fuentes de datos, sin nuevas dependencias de IA,
sin selección ni timing, sin esquema.

---

## 14. Paquetes v1.1 «Ulises» (REC, pendientes de aprobación)
Orden: P0 (con backup fuera de AWS primero, §5.1) → decisión de plan AWS →
P1 → P4 → P3 → P6 → P2 → P5. VA-16 ya corregido.
Si un hallazgo de seguridad resulta crítico, P4.7 se adelanta.

| Paquete | Objetivo |
|---|---|
| P0 | Commit limpio + tag, hash visible, backup off-site cifrado, restore probado, delete_all con backup previo |
| P1 | Preflight en UI con trade_check y registro de decisión; banner del plan; analysis/{t} subordinado al plan; rutina semanal |
| P2 | Modo hibernación; estrés uniforme rotulado ilustrativo; HHI con ETF_META; marco único de pérdida |
| P3 | evaluable:false con precio faltante; TTL para fallback de captura; etiqueta en resultado_real; verify_all con evidencia; tests de invariantes |
| P4 | Canario de fuentes; red-team de plan_guard; léxico prohibido; tope de gasto IA; política de datos al proveedor; enlace de entrada rotable; backups cifrados |
| P5 | Costo de la herramienta con factura; comparación contra retorno; «impuesto en Perú: SIN DATO» en rebalanceo |
| P6 | pending_changes con enfriamiento y confirmación tipada para limits/profile; elección fechada de ruta |
| P7 | Fase 2: bitácora append-only (prioridad 1), vínculos, cumplimiento hacia adelante, estrés por activo, look-through, reconciliación Hapi, fiscal, UCITS |

---

## 15. Gate conductual (propuesta de cambio de spec)
Problema: «4 semanas de rutina» no mapea a aportes cada ≈ 26 semanas.
Propuesta: rutina semanal ≤ 5 min (registrar ahorro_soles, confirmar si se operó
en Hapi, registrar decisión si hubo operación).
Gate a Fase 2: P0 completo + 4 semanas consecutivas con ≥ 1 ahorro_soles y 0
desvíos sin documentar. Usa tablas existentes. Limitación: ahorro_soles es
borrable (sin UPDATE, con DELETE); no es a prueba de manipulación hasta Fase 2.

---

## 16. Lo que funciona y no se toca
Etiquetas de certeza · borrador → confirmación · fail-closed de la regla en ambos
sentidos · fuente única de la regla (chat y trade_check) · puerta única a la IA
con plan_guard antes del proveedor · suite sin red con pruebas red separadas ·
descartes metodológicos (Monte Carlo, XIRR, Kelly, CVaR) · orden de lectura:
plan → motor → decisión del usuario → Luna.

---

## 17. Escalado
Conflicto con una instrucción del usuario: detener, citar file:line o texto,
pedir decisión explícita, no improvisar.
Conflicto con una instrucción previa del agente: gana este archivo; documentar
la discrepancia; pedir actualización formal.

Fin. Toda modificación requiere aprobación del usuario y se registra en
docs/DECISIONES.md.
