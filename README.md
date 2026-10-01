# Inversor Hapi IA — MVP funcional

Sistema de apoyo a decisiones de inversión para usuarios de Hapi. **Transforma datos con fuente y fecha en decisiones explicables.** No promete rentabilidad, no inventa cifras, no presenta estimaciones como certezas y **nunca ejecuta operaciones**: propone, argumenta y registra; la ejecución la hace el usuario en su bróker.

---

## 1. Definición del producto

Para cada activo el sistema responde: qué está ocurriendo (precio con fuente/fecha/estado), si cambió el negocio o solo el precio (fundamentales vs. cotización), si la valoración es razonable (múltiplos + DCF por escenarios con supuestos editables), qué riesgos existen (concentración, correlación, estrés), qué alternativa conviene (comprar / agregar gradualmente / mantener / reducir / vender / esperar / sustituir / efectivo, cada una con argumentos a favor y en contra), qué condiciones invalidarían la decisión, y cuándo revisar de nuevo.

## 2. Alcance del MVP

Registro/validación de cartera (manual o por captura de Hapi, siempre marcada *pendiente de verificación*), precios reales de Yahoo Finance con fuente y antigüedad clasificada (actual / reciente / desactualizado) + ingreso manual, fundamentales manuales con fuente y fecha obligatorias, análisis fundamental por dimensiones (0–10) que reporta lo que falta en vez de inventarlo, valoración por 3 escenarios DCF (rangos, nunca precio objetivo único), análisis técnico complementario (SMA, RSI, volatilidad, drawdown), motor de decisiones con checklist obligatorio antes de promediar a la baja, gestión de riesgo (pesos, HHI, sectores, correlación NVDA↔MSFT, límites configurables, estrés −10/−20/−30/−50%), radar de oportunidades que puntúa un universo fijo de 78 empresas grandes de EE.UU. más la watchlist y la cartera del usuario con precio (Yahoo) y fundamentales del 10-K (SEC), alertas clasificadas, diario de inversión (tesis antes, evaluación proceso-vs-resultado después) e historial de decisiones. App local de un solo usuario: sin login.

## 3. Funciones incluidas y excluidas

**Excluidas del MVP (deliberadamente):** ejecución automática de órdenes (prohibida en esta versión); integración directa con la cuenta Hapi (no se piden credenciales de Hapi); correlaciones estadísticas calculadas (v2, con histórico suficiente); multi-divisa completa (el MVP asume USD y lo declara).

## 4. Historias de usuario

1. Como inversionista, cargo mi cartera de Hapi y el sistema valida cantidades, costos y rendimientos, marcando inconsistencias y datos pendientes.
2. Como inversionista, actualizo precios con un clic y siempre veo fuente, fecha/hora y si el dato es actual.
3. Como inversionista, pido un análisis de NVDA y recibo una decisión propuesta con argumentos, confianza, alternativas comparadas y la pregunta obligatoria («¿la comprarías hoy?»).
4. Como inversionista con una posición en rojo, el sistema me obliga a pasar el checklist de promediar antes de sugerir agregar.
5. Como inversionista, registro mi tesis antes de operar y la evalúo después separando proceso de resultado.
6. Como inversionista, recibo alertas cuando NVDA excede mi límite por empresa (74.5% > 25%) y cuando dos posiciones están correlacionadas.

## 5. Flujo de navegación

Hoy (avisos del plan, tarjetas «Tu marcador» —lo que salió de tu bolsillo vs. lo que vale hoy y el fantasma S&P 500— y «Tu alcancía» —ahorro en soles con meta EOQ—, chat de Luna; el motor y lo técnico quedan plegados en «Avanzado») → Cartera (foto de Hapi, posiciones y precios; herramientas avanzadas plegadas) → ¿Compro o vendo? (evalúa una operación concreta: precio vivo, cartera antes/después, límites, propuesta del motor y segunda opinión de Luna; opción de guardar en el diario) → Diario (tesis y evaluación + historial de decisiones) → Oportunidades (radar que ordena por veredicto —barata y buena / precio justo / buena pero cara / cuidado / faltan datos— según calidad media de los scores y margen de seguridad del DCF base con crecimiento del 10-K acotado a 0–15 %; el usuario solo agrega el ticker y el sistema descarga precio y 10-K; los candidatos con notas propias se conservan en una sección plegada) → Ajustes (perfil de riesgo, límites y zona de peligro).

## 6. Modelo de datos

SQLite (`app/db.py`): `users` (una sola fila local, sin login), `positions` (con `source` y `verified`), `trades`, `trade_sources` (procedencia de cada orden importada), `cash`, `prices` (histórico: cada precio con fuente, moneda y fecha/hora), `fundamentals` (JSON + fuente, fecha, período y unidades de informes confirmados), `journal` (tesis + evaluación posterior), `decisions` (propuesta y sus argumentos vs. elección del usuario), `candidates`, `settings` (perfil de riesgo, límites y ajustes del plan como la tarifa de depósito o el vencimiento del W-8BEN), `contributions` (depósitos, retiros, dividendos y ahorro en soles contados por texto, captura o historial, con fingerprint para detectar duplicados). Las alertas se calculan en vivo en `GET /api/alerts`, no tienen tabla. La migración de columnas de fundamentales es aditiva; no borra filas anteriores.

## 7. Arquitectura

FastAPI + SQLite. La configuración del proveedor de IA y su llamada viven en `ai_provider.py` (capa única). Módulos: `marketdata.py` (Yahoo Finance chart API sin clave + clasificación de antigüedad + indicadores técnicos, incluidos ATR14 y **niveles por volatilidad**: stop = precio − 2·ATR, toma parcial = precio + 3·ATR, zona de entrada escalonada, semáforo de la acción descuento/estirada/bajista/neutral; siempre etiquetados «regla técnica, no predicción»), `marketpulse.py` (**pulso de mercado**: SPY, QQQ, IWM, ^VIX, USO, TLT, GLD → semáforo normal/cauteloso/miedo por VIX y medias del S&P 500, tipo de día rojo/verde/tranquilo y una lectura determinista con las cifras reales; caché en memoria de 15 min, y de 10 min para los niveles por ticker), `analysis.py` (scores fundamentales, múltiplos, DCF por escenarios con supuestos editables), `risk.py` (pesos, HHI, sectores, correlación, límites, estrés), `decisions.py` (motor de decisiones, checklist de promediar, perfil de riesgo), `photosync.py` / `fundsync.py` / `tradesync.py` (extracción por foto de cartera, fundamentales y órdenes), `ai_assistant.py` / `ai_review.py` (consultas y revisión con Luna, con la regla determinista del plan: mientras el ETF esté bajo su meta, Luna no recomienda comprar acciones individuales), `scoreboard.py` (marcador de bolsillo y fantasma SPY a retorno total con `adjclose`), `alcancia.py` (meta EOQ del ahorro en soles), `flowsync.py` (texto/captura/historial de movimientos con la IA; solo entran movimientos «Terminado»), `radar.py` (universo de 78 emisoras de EE.UU. con 10-K y función `screen` pura que combina calidad media y margen de seguridad). Los endpoints viven en `app/routes/` por dominio (`profile`, `portfolio`, `market`, `trades`, `ai`, `decisions`, `radar`, `system`, `marcador` —`GET /api/marcador` y `POST/GET/DELETE /api/flows*`—) y `main.py` ensambla la app y sirve el frontend. Frontend: SPA sin dependencias (`static/index.html` + `app.css` + `app.js`, 6 pantallas, servida con `no-cache`). Separación explícita HECHO / CÁLCULO / ESTIMACIÓN / FALTANTE en las respuestas.

## 8. Fuentes de información propuestas

- **Precios e histórico:** Yahoo Finance chart API (implementada; cada dato guarda fuente y fecha; fallo → ingreso manual). Alternativas para v2: Alpha Vantage, Finnhub, Polygon (requieren clave).
- **Mercado hoy y niveles:** `GET /api/market/pulse` (tarjeta «Mercado hoy» en *Hoy*; también entra resumido en `trade_check` como `mercado_hoy` y en el contexto de Luna) y `GET /api/levels/{ticker}` (plan de niveles ATR al desplegar una fila en *Cartera*, con distancias desde tu costo promedio; `trade_check` devuelve los mismos `niveles` y *¿Compro o vendo?* prellena tesis, riesgos y condición de invalidación del diario solo con esas cifras). Si Yahoo falla, `mercado_hoy` es `null` y nada más se rompe. Son reglas técnicas por volatilidad con fuente y hora, no predicciones.
- **Fundamentales:** SEC EDGAR (API pública, sin clave): `app/secdata.py` descarga los `companyfacts` del último 10-K con `POST /api/fundamentals/{ticker}/sec` y `trade_check` los usa solo si faltan. ETF y fondos no presentan 10-K (el endpoint devuelve 404). El radar (`GET /api/radar`, `POST /api/radar/refresh`, `POST /api/radar/{ticker}`) reutiliza el mismo mecanismo: el GET solo lee lo guardado y los POST descargan precios y 10-K por ticker sin abortar ante errores. Alternativas: ingreso manual o foto de informe revisada; ambas exigen fuente y fecha.
- **Nunca** se usan cifras sin fuente ni fecha.

## 9. Instalación

```bash
cd inversor-hapi
pip install -r requirements.txt
python run_local.py
```

En Windows puedes abrir `iniciar-local.cmd` con doble clic. El iniciador elige un puerto libre, espera a que la app responda y abre **esa instancia** en el navegador; evita confundirla con un servidor antiguo que siga abierto en `8100`. Mantén la terminal abierta mientras uses la app y ciérrala con Ctrl+C. Si no quieres abrir el navegador automáticamente, usa `python run_local.py --no-browser`. Puedes pedir un puerto concreto con `--port 8100`: si está ocupado, mostrará un error en vez de conectarte a otra instancia.

**Solo uso local:** escucha exclusivamente en `127.0.0.1`, no publica la aplicación en internet. Guarda tu `inversor.db` y `.secrets/` fuera de Git y haz copia de seguridad antes de moverla de equipo. Para publicar la app se necesitan primero sesiones con caducidad, TLS, límites de tamaño y frecuencia, y proteger el registro y las llamadas con coste a la IA. Variables de entorno opcionales: `INVERSOR_DB` (ruta de la base de datos); la configuración de Luna conserva los mecanismos de `.secrets/ai.env` o variables de entorno.

### Uso día a día

Una vez abierta la app en el navegador, el recorrido habitual es:

1. **Hoy** — panel inicial: avisos del plan (meta de alcancía, inactividad en Hapi, W-8BEN), «Tu marcador» (depósitos netos, costos estimados/calculados, resultado real vs. fantasma S&P 500), «Tu alcancía» (cuéntale «guardé 80 soles», pega tu historial de Hapi o sube una captura; confirma antes de guardar) y el chat de Luna; las herramientas avanzadas quedan plegadas en «Avanzado».
2. **Cartera** — carga tu cartera con una captura de Hapi (o a mano), verifica las posiciones y actualiza precios. Al desplegar una fila ves los niveles ATR. El historial de órdenes y la conciliación de costo siguen disponibles dentro de **Herramientas avanzadas → Historial de órdenes y costo promedio**; no intervienen en el marcador de bolsillo ni deben importarse para usar la rutina diaria.
3. **¿Compro o vendo?** — escribe ticker, acción y cantidad/precio: la app devuelve precio vivo, impacto en tu cartera, límites, la propuesta del motor y la «Segunda opinión de Luna». Puedes guardar la tesis directo en el diario.
4. **Diario** — registra la tesis antes de operar y evalúala después separando proceso de resultado; «Cuestionar tesis con Luna» propone hipótesis en contra.
5. **Oportunidades** — radar que puntúa 78 emisoras grandes de EE.UU. más tu watchlist: solo agregas el ticker y el sistema descarga el precio (Yahoo) y el 10-K (SEC), y lo ordena por veredicto.
6. **Ajustes** — perfil de riesgo, límites por empresa/sector y zona de peligro (borrado total de datos).

### Consultar a Luna

El chat de Luna en **Hoy** reutiliza el modelo y la configuración de la sincronización por foto (`INVERSOR_AI_API_KEY`, `INVERSOR_AI_BASE_URL`, `INVERSOR_AI_MODEL`, `INVERSOR_AI_API_STYLE` en variables de entorno o `.secrets/ai.env`). `GET /api/assistant/status` muestra si está disponible y `POST /api/assistant/ask` recibe `{"question": "...", "history": [...]}` (hasta 8 turnos previos, solo para entender repreguntas; la conversación no se guarda). No necesitas configurar una segunda clave.

Al preguntar, se envían al proveedor de IA la pregunta y un resumen de tus posiciones, efectivo, precios con fuente/fecha, riesgo calculado, parte del perfil de riesgo, fundamentales registrados y hasta cinco tesis recientes. **En esa consulta no se envían fotos, credenciales ni correo.** Cada pregunta supone una llamada al proveedor y puede tener coste según tu plan; las respuestas no se guardan ni actualizan la cartera, y la consulta no descarga precios nuevos. La IA debe señalar datos ausentes o viejos, pero revisa siempre sus cifras y fuentes antes de tomar decisiones. No hay órdenes automáticas.

### Luna en informes, historial y diario

- **Informe:** en *¿Compro o vendo? → Ver análisis completo → Fundamentales*, sube una foto de un informe anual o TTM, o pulsa «Cargar desde la SEC (10-K oficial)» para usar los datos publicados en EDGAR (`POST /api/fundamentals/{ticker}/sec`; reemplazar datos existentes pide confirmación). `POST /api/fundamentals/photo/analyze` devuelve solo un borrador. Corrige la tabla, confirma la fuente exacta, fecha de cierre, período y las escalas independientes de dinero y acciones antes de guardar con `POST /api/fundamentals/{ticker}/photo/save`. El EPS es por acción y no se escala. Las cifras trimestrales aisladas no se guardan para el DCF; reemplazar datos existentes requiere consentimiento expreso. Lo ilegible permanece vacío, no se estima. El ingreso manual sigue disponible.
- **Operaciones:** en *Cartera → Herramientas avanzadas → Historial de órdenes y costo promedio*, sube una captura de órdenes **ejecutadas** del historial de Hapi. `POST /api/trades/photo/analyze` solo prepara filas editables: confirma cada compra o venta, fecha, cantidad, precio por acción, comisión (cero solo si consta), moneda USD y fuente antes de importar con `POST /api/trades/import`. El modelo no completa comisiones ausentes. Los posibles duplicados se muestran y requieren nueva confirmación; no se ignoran automáticamente. Consulta `GET /api/trades?ticker=...` para revisar el libro.
- **Costo promedio:** importar operaciones **nunca** cambia la cartera. Solo si confirmas que tienes **todas** las compras y ventas desde el inicio, que la posición existente está verificada en USD y que sus acciones coinciden con el libro (tolerancia de 0,00001 acción), puedes pedir la vista previa de `POST /api/trades/{ticker}/reconcile`. Para aplicar, debes confirmar además que **no hubo splits, transferencias ni ajustes de costo o acciones sin modelar**: este libro solo sabe procesar compras y ventas. Una segunda confirmación vinculada a esa vista previa aplica únicamente el costo invertido y promedio, sin modificar las acciones y dejando la posición pendiente de nueva verificación. Las compras incluyen su comisión; las ventas descuentan costo proporcional, y la comisión de venta no altera el costo remanente. SQLite almacena posiciones y operaciones como `REAL`: puede perderse precisión respecto del cálculo decimal.
- **Tesis:** en *Diario*, «Cuestionar tesis con Luna» utiliza una entrada ya guardada y devuelve tres hipótesis en contra con preguntas verificables; no cambia la tesis. **Explicar con Luna** lee argumentos de una propuesta determinista ya guardada; las propuestas antiguas sin argumentos conservados no pueden explicarse sin inventarlos. Ninguna consulta a Luna registra una operación, descarga precios ni cambia la decisión del motor.
- **Segunda opinión:** en *¿Compro o vendo?*, tras evaluar una operación (`POST /api/trade_check`), «Segunda opinión de Luna» (`POST /api/trade_check/{id}/luna`) devuelve resumen, puntos a favor y en contra y preguntas por verificar. Luna solo puede citar cifras que ya están en la evaluación guardada; si menciona otras, la respuesta se rechaza o se reintenta una vez.

Las fotos de informes y órdenes, así como los fragmentos de tesis o de decisiones necesarios para una consulta, **sí se envían al proveedor configurado**. No se guardan las imágenes en esta app. Cada análisis y revisión genera una llamada externa con posible costo; revisa la política de datos de tu proveedor antes de subir documentos sensibles. Estos flujos están pensados solo para uso local.

## 10. Pruebas

```bash
python -m pytest tests/ -q     # cálculo, riesgo, foto, SEC, radar, operaciones, marcador y API
python -m compileall -q app
node --check static/app.js
node --test tests/frontend.test.js   # marcador, estados sin dato y resguardo del libro
```

Las pruebas no dependen de la red: `tests/conftest.py` bloquea la descarga de Yahoo en todas salvo la única marcada `@pytest.mark.red` (fetch real tolerante a fallos) y limpia las cachés de pulso y niveles entre pruebas. Para futuras mejoras de esta interfaz existe la skill local `.agents/skills/hapi-frontend/SKILL.md`.

## 11. Riesgos y limitaciones

- La API de Yahoo no es un contrato formal: puede cambiar; por eso existe el ingreso manual y todo precio declara su fuente.
- El DCF depende por completo de los supuestos: el sistema los muestra y los hace editables, pero supuestos malos producen rangos malos (por eso hay 3 escenarios y margen de seguridad, no un precio objetivo).
- Los scores fundamentales usan umbrales genéricos; sirven para comparar, no como verdad absoluta. El radar cubre un universo fijo de empresas grandes y líquidas de EE.UU. que presentan 10-K (sin ETF ni emisoras que reportan 20-F): no es toda la bolsa ni una recomendación.
- La detección de correlación usa grupos conocidos (tecnología/IA), no covarianzas calculadas (v2).
- **No es asesoría financiera regulada.** El análisis no genera una propuesta si falta una cotización de mercado vigente: un valor extraído de una foto o un precio caducado no la sustituyen. Con datos fundamentales insuficientes o perfil incompleto, la confianza sigue siendo baja.
- Las capturas se conservan como valores de referencia, pero no se suman al **valor actual** ni generan P/L actual. Si alguna posición carece de cotización vigente en USD, el total, la concentración y las propuestas de cartera quedan pendientes hasta actualizarla. Si falta un costo invertido, el resultado y el rendimiento se muestran como no calculables. No se convierten divisas sin un tipo de cambio fechado y verificado; el efectivo no USD bloquea cálculos de riesgo y decisiones.
- Al editar o volver a importar una posición, se pierde la marca de «verificada» hasta que el usuario la confirme otra vez. Los precios manuales requieren valor positivo, fuente y fecha válida; las fechas futuras se rechazan y los precios futuros ya existentes no se presentan como actuales.
- Pendiente para uso multiusuario: los precios manuales se guardan en una tabla compartida por ticker. Aislarlos por usuario exige migrar el esquema y revisar los registros históricos antes de usar la app con otras cuentas.

## 12. Plan para versiones posteriores

Correlaciones y VaR calculados con histórico; multi-divisa (PEN/USD con tipo de cambio fechado); notificaciones push/correo para alertas; comparador de candidatos contra posiciones con datos en vivo. La ejecución de órdenes permanece fuera del producto.
