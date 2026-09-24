# Inversor Hapi IA — MVP funcional

Sistema de apoyo a decisiones de inversión para usuarios de Hapi. **Transforma datos con fuente y fecha en decisiones explicables.** No promete rentabilidad, no inventa cifras, no presenta estimaciones como certezas y **nunca ejecuta operaciones**: propone, argumenta y registra; la ejecución la hace el usuario en su bróker.

---

## 1. Definición del producto

Para cada activo el sistema responde: qué está ocurriendo (precio con fuente/fecha/estado), si cambió el negocio o solo el precio (fundamentales vs. cotización), si la valoración es razonable (múltiplos + DCF por escenarios con supuestos editables), qué riesgos existen (concentración, correlación, estrés), qué alternativa conviene (comprar / agregar gradualmente / mantener / reducir / vender / esperar / sustituir / efectivo, cada una con argumentos a favor y en contra), qué condiciones invalidarían la decisión, y cuándo revisar de nuevo.

## 2. Alcance del MVP

Registro/validación de cartera (con la cartera NVDA+MSFT reportada por el usuario precargable y marcada *pendiente de verificación*), precios reales de Yahoo Finance con fuente y antigüedad clasificada (actual / reciente / desactualizado) + ingreso manual, fundamentales manuales con fuente y fecha obligatorias, análisis fundamental por dimensiones (0–10) que reporta lo que falta en vez de inventarlo, valoración por 3 escenarios DCF (rangos, nunca precio objetivo único), análisis técnico complementario (SMA, RSI, volatilidad, drawdown), motor de decisiones con checklist obligatorio antes de promediar a la baja, gestión de riesgo (pesos, HHI, sectores, correlación NVDA↔MSFT, límites configurables, estrés −10/−20/−30/−50%), simulador de escenarios, buscador de oportunidades con datos aportados por el usuario, alertas clasificadas, diario de inversión (tesis antes, evaluación proceso-vs-resultado después), historial de decisiones y auditoría.

## 3. Funciones incluidas y excluidas

**Excluidas del MVP (deliberadamente):** ejecución automática de órdenes (prohibida en esta versión); integración directa con la cuenta Hapi (no se piden credenciales de Hapi); descarga automática de fundamentales (las capturas se revisan manualmente, no se presentan como datos verificados automáticamente); correlaciones estadísticas calculadas (v2, con histórico suficiente); multi-divisa completa (el MVP asume USD y lo declara).

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

SQLite (`app/db.py`): `users`, `sessions`, `positions` (con `source` y `verified`), `trades`, `trade_sources` (procedencia de cada orden importada), `cash`, `prices` (histórico: cada precio con fuente, moneda y fecha/hora), `fundamentals` (JSON + fuente, fecha, período y unidades de informes confirmados), `journal` (tesis + evaluación posterior), `decisions` (propuesta y sus argumentos vs. elección del usuario), `candidates`, `alerts`, `settings` (perfil de riesgo y límites), `audit_log`. La migración de columnas de fundamentales es aditiva; no borra filas anteriores.

## 7. Arquitectura

FastAPI + SQLite. Módulos: `marketdata.py` (Yahoo Finance chart API sin clave + clasificación de antigüedad + indicadores técnicos), `analysis.py` (scores fundamentales, múltiplos, DCF por escenarios con supuestos editables), `risk.py` (pesos, HHI, sectores, correlación, límites, estrés), `decisions.py` (motor de decisiones, checklist de promediar, simulador, perfil de riesgo), `main.py` (API + formato de recomendación del Módulo 14). Frontend: SPA sin dependencias (`static/index.html`, 12 pantallas). Separación explícita HECHO / CÁLCULO / ESTIMACIÓN / FALTANTE en las respuestas.

## 8. Fuentes de información propuestas

- **Precios e histórico:** Yahoo Finance chart API (implementada; cada dato guarda fuente y fecha; fallo → ingreso manual). Alternativas para v2: Alpha Vantage, Finnhub, Polygon (requieren clave).
- **Fundamentales:** informes 10-K/10-Q del emisor (ir.nvidia.com, microsoft.com/investor) ingresados por el usuario con fuente y fecha; v2 puede automatizar con SEC EDGAR (API pública).
- **Nunca** se usan cifras sin fuente ni fecha.

## 9. Instalación

```bash
cd inversor-hapi
pip install -r requirements.txt
python run_local.py
```

En Windows puedes abrir `iniciar-local.cmd` con doble clic. El iniciador elige un puerto libre, espera a que la app responda y abre **esa instancia** en el navegador; evita confundirla con un servidor antiguo que siga abierto en `8100`. Mantén la terminal abierta mientras uses la app y ciérrala con Ctrl+C. Si no quieres abrir el navegador automáticamente, usa `python run_local.py --no-browser`. Puedes pedir un puerto concreto con `--port 8100`: si está ocupado, mostrará un error en vez de conectarte a otra instancia.

**Solo uso local:** escucha exclusivamente en `127.0.0.1`, no publica la aplicación en internet. Guarda tu `inversor.db` y `.secrets/` fuera de Git y haz copia de seguridad antes de moverla de equipo. Para publicar la app se necesitan primero sesiones con caducidad, TLS, límites de tamaño y frecuencia, y proteger el registro y las llamadas con coste a la IA. Variables de entorno opcionales: `INVERSOR_DB` (ruta de la base de datos); la configuración de Luna conserva los mecanismos de `.secrets/ai.env` o variables de entorno.

### Consultar a Luna

La sección **Consultar a Luna** reutiliza el modelo y la configuración de la sincronización por foto (`INVERSOR_AI_API_KEY`, `INVERSOR_AI_BASE_URL`, `INVERSOR_AI_MODEL`, `INVERSOR_AI_API_STYLE` en variables de entorno o `.secrets/ai.env`). `GET /api/assistant/status` muestra si está disponible y `POST /api/assistant/ask` recibe `{"question": "..."}`; ambos requieren sesión. No necesitas configurar una segunda clave.

Al preguntar, se envían al proveedor de IA la pregunta y un resumen de tus posiciones, efectivo, precios con fuente/fecha, riesgo calculado, parte del perfil de riesgo, fundamentales registrados y hasta cinco tesis recientes. **En esa consulta no se envían fotos, credenciales ni correo.** Cada pregunta supone una llamada al proveedor y puede tener coste según tu plan; las respuestas no se guardan ni actualizan la cartera, y la consulta no descarga precios nuevos. La IA debe señalar datos ausentes o viejos, pero revisa siempre sus cifras y fuentes antes de tomar decisiones. No hay órdenes automáticas.

### Luna en informes, historial y diario

- **Informe:** en *Analizar un activo → Fundamentales*, sube una foto de un informe anual o TTM. `POST /api/fundamentals/photo/analyze` devuelve solo un borrador. Corrige la tabla, confirma la fuente exacta, fecha de cierre, período y las escalas independientes de dinero y acciones antes de guardar con `POST /api/fundamentals/{ticker}/photo/save`. El EPS es por acción y no se escala. Las cifras trimestrales aisladas no se guardan para el DCF; reemplazar datos existentes requiere consentimiento expreso. Lo ilegible permanece vacío, no se estima. El ingreso manual sigue disponible.
- **Operaciones:** en *Cartera*, sube una captura de órdenes **ejecutadas** del historial de Hapi. `POST /api/trades/photo/analyze` solo prepara filas editables: confirma cada compra o venta, fecha, cantidad, precio por acción, comisión (cero solo si consta), moneda USD y fuente antes de importar con `POST /api/trades/import`. El modelo no completa comisiones ausentes. Los posibles duplicados se muestran y requieren nueva confirmación; no se ignoran automáticamente. Consulta `GET /api/trades?ticker=...` para revisar el libro.
- **Costo promedio:** importar operaciones **nunca** cambia la cartera. Solo si confirmas que tienes **todas** las compras y ventas desde el inicio, que la posición existente está verificada en USD y que sus acciones coinciden con el libro (tolerancia de 0,00001 acción), puedes pedir la vista previa de `POST /api/trades/{ticker}/reconcile`. Para aplicar, debes confirmar además que **no hubo splits, transferencias ni ajustes de costo o acciones sin modelar**: este libro solo sabe procesar compras y ventas. Una segunda confirmación vinculada a esa vista previa aplica únicamente el costo invertido y promedio, sin modificar las acciones y dejando la posición pendiente de nueva verificación. Las compras incluyen su comisión; las ventas descuentan costo proporcional, y la comisión de venta no altera el costo remanente. SQLite almacena posiciones y operaciones como `REAL`: puede perderse precisión respecto del cálculo decimal.
- **Tesis:** en *Diario*, «Cuestionar tesis con Luna» utiliza una entrada ya guardada y devuelve tres hipótesis en contra con preguntas verificables; no cambia la tesis. **Explicar con Luna** lee argumentos de una propuesta determinista ya guardada; las propuestas antiguas sin argumentos conservados no pueden explicarse sin inventarlos. Ninguna consulta a Luna registra una operación, descarga precios ni cambia la decisión del motor.

Las fotos de informes y órdenes, así como los fragmentos de tesis o de decisiones necesarios para una consulta, **sí se envían al proveedor configurado**. No se guardan las imágenes en esta app. Cada análisis y revisión genera una llamada externa con posible costo; revisa la política de datos de tu proveedor antes de subir documentos sensibles. Estos flujos están pensados solo para uso local.

## 10. Pruebas

```bash
python -m pytest tests/ -q     # cálculo, riesgo, integridad de precios, cartera, foto, IA y API
```

Las pruebas no dependen de la red (precios manuales); el fetch real se prueba de forma tolerante a fallos.

## 11. Riesgos y limitaciones

- La API de Yahoo no es un contrato formal: puede cambiar; por eso existe el ingreso manual y todo precio declara su fuente.
- El DCF depende por completo de los supuestos: el sistema los muestra y los hace editables, pero supuestos malos producen rangos malos (por eso hay 3 escenarios y margen de seguridad, no un precio objetivo).
- Los scores fundamentales usan umbrales genéricos; sirven para comparar, no como verdad absoluta.
- La detección de correlación usa grupos conocidos (tecnología/IA), no covarianzas calculadas (v2).
- **No es asesoría financiera regulada.** El análisis no genera una propuesta si falta una cotización de mercado vigente: un valor extraído de una foto o un precio caducado no la sustituyen. Con datos fundamentales insuficientes o perfil incompleto, la confianza sigue siendo baja.
- Las capturas se conservan como valores de referencia, pero no se suman al **valor actual** ni generan P/L actual. Si alguna posición carece de cotización vigente en USD, el total, la concentración, el simulador y las propuestas de cartera quedan pendientes hasta actualizarla. Si falta un costo invertido, el resultado y el rendimiento (también en el simulador) se muestran como no calculables. No se convierten divisas sin un tipo de cambio fechado y verificado; el efectivo no USD bloquea cálculos de riesgo y decisiones.
- Al editar o volver a importar una posición, se pierde la marca de «verificada» hasta que el usuario la confirme otra vez. Los precios manuales requieren valor positivo, fuente y fecha válida; las fechas futuras se rechazan y los precios futuros ya existentes no se presentan como actuales.
- Pendiente para uso multiusuario: los precios manuales se guardan en una tabla compartida por ticker. Aislarlos por usuario exige migrar el esquema y revisar los registros históricos antes de usar la app con otras cuentas.

## 12. Plan para versiones posteriores

Descarga verificable de fundamentales vía SEC EDGAR; correlaciones y VaR calculados con histórico; multi-divisa (PEN/USD con tipo de cambio fechado); notificaciones push/correo para alertas; import CSV de operaciones de brókers; comparador de candidatos contra posiciones con datos en vivo. La ejecución de órdenes permanece fuera del producto.
