# Inversor Hapi IA — MVP funcional

Sistema de apoyo a decisiones de inversión para usuarios de Hapi. **Transforma datos con fuente y fecha en decisiones explicables.** No promete rentabilidad, no inventa cifras, no presenta estimaciones como certezas y **nunca ejecuta operaciones**: propone, argumenta y registra; la ejecución la hace el usuario en su bróker.

---

## 1. Definición del producto

Para cada activo el sistema responde: qué está ocurriendo (precio con fuente/fecha/estado), si cambió el negocio o solo el precio (fundamentales vs. cotización), si la valoración es razonable (múltiplos + DCF por escenarios con supuestos editables), qué riesgos existen (concentración, correlación, estrés), qué alternativa conviene (comprar / agregar gradualmente / mantener / reducir / vender / esperar / sustituir / efectivo, cada una con argumentos a favor y en contra), qué condiciones invalidarían la decisión, y cuándo revisar de nuevo.

## 2. Alcance del MVP

Registro/validación de cartera (con la cartera NVDA+MSFT reportada por el usuario precargable y marcada *pendiente de verificación*), precios reales de Yahoo Finance con fuente y antigüedad clasificada (actual / reciente / desactualizado) + ingreso manual, fundamentales manuales con fuente y fecha obligatorias, análisis fundamental por dimensiones (0–10) que reporta lo que falta en vez de inventarlo, valoración por 3 escenarios DCF (rangos, nunca precio objetivo único), análisis técnico complementario (SMA, RSI, volatilidad, drawdown), motor de decisiones con checklist obligatorio antes de promediar a la baja, gestión de riesgo (pesos, HHI, sectores, correlación NVDA↔MSFT, límites configurables, estrés −10/−20/−30/−50%), simulador de escenarios, buscador de oportunidades con datos aportados por el usuario, alertas clasificadas, diario de inversión (tesis antes, evaluación proceso-vs-resultado después), historial de decisiones y auditoría.

## 3. Funciones incluidas y excluidas

**Excluidas del MVP (deliberadamente):** ejecución automática de órdenes (Módulo 15: prohibida en esta versión; si algún día existe integración autorizada con Hapi, cada orden exigirá confirmación explícita nueva); integración directa con la cuenta Hapi (no hay API pública; no se piden credenciales de Hapi); fundamentales automáticos (las fuentes gratuitas fiables requieren clave/licencia — se dejó el ingreso manual con fuente obligatoria); correlaciones estadísticas calculadas (v2, con histórico suficiente); multi-divisa completa (el MVP asume USD y lo declara).

## 4. Historias de usuario

1. Como inversionista, cargo mi cartera de Hapi y el sistema valida cantidades, costos y rendimientos, marcando inconsistencias y datos pendientes.
2. Como inversionista, actualizo precios con un clic y siempre veo fuente, fecha/hora y si el dato es actual.
3. Como inversionista, pido un análisis de NVDA y recibo una decisión propuesta con argumentos, confianza, alternativas comparadas y la pregunta obligatoria («¿la comprarías hoy?»).
4. Como inversionista con una posición en rojo, el sistema me obliga a pasar el checklist de promediar antes de sugerir agregar.
5. Como inversionista, simulo caídas de −10/−20/−30% y veo el impacto en valor y concentración.
6. Como inversionista, registro mi tesis antes de operar y la evalúo después separando proceso de resultado.
7. Como inversionista, recibo alertas cuando NVDA excede mi límite por empresa (74.5% > 25%) y cuando dos posiciones están correlacionadas.

## 5. Flujo de navegación

Inicio (panel) → Cartera (cargar/validar/precios) → Perfil de riesgo → Análisis y decisión (fundamentales → supuestos → decisión → registrar) → Comparador → Simulador → Oportunidades → Diario → Alertas → Historial → Configuración.

## 6. Modelo de datos

SQLite (`app/db.py`): `users`, `sessions`, `positions` (con `source` y `verified`), `trades`, `cash`, `prices` (histórico: cada precio con fuente, moneda y fecha/hora), `fundamentals` (JSON + fuente + fecha obligatorias), `journal` (tesis + evaluación posterior), `decisions` (propuesta vs. decisión del usuario, autorización nunca reutilizable), `candidates`, `alerts`, `settings` (perfil de riesgo y límites), `audit_log`.

## 7. Arquitectura

FastAPI + SQLite. Módulos: `marketdata.py` (Yahoo Finance chart API sin clave + clasificación de antigüedad + indicadores técnicos), `analysis.py` (scores fundamentales, múltiplos, DCF por escenarios con supuestos editables), `risk.py` (pesos, HHI, sectores, correlación, límites, estrés), `decisions.py` (motor de decisiones, checklist de promediar, simulador, perfil de riesgo), `main.py` (API + formato de recomendación del Módulo 14). Frontend: SPA sin dependencias (`static/index.html`, 12 pantallas). Separación explícita HECHO / CÁLCULO / ESTIMACIÓN / FALTANTE en las respuestas.

## 8. Fuentes de información propuestas

- **Precios e histórico:** Yahoo Finance chart API (implementada; cada dato guarda fuente y fecha; fallo → ingreso manual). Alternativas para v2: Alpha Vantage, Finnhub, Polygon (requieren clave).
- **Fundamentales:** informes 10-K/10-Q del emisor (ir.nvidia.com, microsoft.com/investor) ingresados por el usuario con fuente y fecha; v2 puede automatizar con SEC EDGAR (API pública).
- **Nunca** se usan cifras sin fuente ni fecha.

## 9. Instalación

```bash
cd inversor-hapi
pip install fastapi uvicorn pytest httpx     # requirements.txt
uvicorn app.main:app --reload --port 8100
# http://localhost:8100 → crear cuenta → "Cargar mi cartera de Hapi" → Actualizar precios
```

Variables de entorno: `INVERSOR_DB` (ruta de la base de datos).

## 10. Pruebas

```bash
python3 -m pytest tests/ -q    # 16 pruebas: staleness, múltiplos, DCF, riesgo/concentración,
                               # motor de decisiones, simulador, validación, diario, alertas, API E2E
```

Las pruebas no dependen de la red (precios manuales); el fetch real se prueba de forma tolerante a fallos.

## 11. Riesgos y limitaciones

- La API de Yahoo no es un contrato formal: puede cambiar; por eso existe el ingreso manual y todo precio declara su fuente.
- El DCF depende por completo de los supuestos: el sistema los muestra y los hace editables, pero supuestos malos producen rangos malos (por eso hay 3 escenarios y margen de seguridad, no un precio objetivo).
- Los scores fundamentales usan umbrales genéricos; sirven para comparar, no como verdad absoluta.
- La detección de correlación usa grupos conocidos (tecnología/IA), no covarianzas calculadas (v2).
- **No es asesoría financiera regulada.** El sistema recomienda esperar cuando falta evidencia y degrada la confianza a «baja» si el perfil de riesgo está incompleto o el precio no es actual.

## 12. Plan para versiones posteriores

Fundamentales automáticos vía SEC EDGAR; correlaciones y VaR calculados con histórico; multi-divisa (PEN/USD con tipo de cambio fechado); notificaciones push/correo para alertas; import CSV de brókers; comparador de candidatos contra posiciones con datos en vivo; análisis asistido por LLM (con citas verificables) para resumir informes trimestrales; y, solo si existe una vía comercial y técnicamente autorizada con Hapi, ejecución con confirmación explícita por orden, precio límite, vigencia y auditoría (nunca reutilizando autorizaciones).
