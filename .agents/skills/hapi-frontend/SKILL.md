---
name: hapi-frontend
description: Diseña y mejora la SPA local de Inversor Hapi: marcador de bolsillo, alcancía y revisión humana de datos financieros, sin falsear cifras ni añadir fricción conductual.
---

# Interfaz de Inversor Hapi

Usa esta skill cuando edites `static/index.html`, `static/app.css` o `static/app.js`. Complementa `frontend-design`: primero define la jerarquía del trabajo real del usuario y critica la solución antes de construir. Lee `docs/BRIEF.md` y las rutas/estructuras que alimentan la vista; no trates el handoff como fuente de cifras en vivo.

## La pregunta de cada pantalla

- **Hoy**: ¿cuánto salió de mi bolsillo, qué parte del costo es estimación, cuánto vale la cartera con fuente/fecha y qué dato falta? El fantasma SPY es comparación, no mérito atribuido. Debajo: alcancía y registro por borrador → confirmación; Luna escucha, no decide.
- **Cartera**: posiciones verificadas y fuente del precio antes que botones. La foto de Hapi entra como borrador editable; no marca una captura parcial como cartera completa. El libro de órdenes y la conciliación son herramientas avanzadas: no borrar tablas ni órdenes para despejar la interfaz.
- **Antes de operar**: mostrar límites, alternativas y tesis. La app nunca ejecuta operaciones; la regla del ETF va antes de la IA.

## Identidad y composición

Conserva el carácter del producto: verde pizarra `#0e1f1c`, acción `#0d6e5f`, fondo `#f5f7f9`, tinta `#15222e`, cautela `#b54708`. Evita degradados decorativos o rediseñar toda la SPA por moda. Usa la tipografía del sistema existente, cifras tabulares para alinear importes y texto legible en móvil. La pieza distintiva es la **cuenta de bolsillo**: depósitos netos + costo de depósito = dinero puesto; valor verificado − dinero puesto = resultado, con fuente/fecha visible. No conviertas esa cuenta en cuatro tarjetas idénticas ni hagas del color positivo una promesa de rentabilidad.

## Barreras de verdad

- No pongas `0` ni `—` con apariencia de cero cuando la API devuelve `null`: di «sin dato» y explica qué falta. No introduzcas cifras de ejemplos reales como valores de la UI.
- HECHO / CÁLCULO / ESTIMACIÓN son etiquetas de los datos, no adornos. Si el costo es ESTIMACIÓN, expresa aproximación; si es CÁLCULO, no escribas `~` por costumbre. Nunca uses el TC implícito para calcular gastos ni dobles dividendos/comisiones ya netos.
- Las fuentes y fechas acompañan cada resultado monetario que se presenta como actual. Usa `textContent` o `esc()` para todo texto del proveedor/usuario; conserva errores accionables y estados de carga.
- No crees avisos del plan adicionales a los tres de Fase 1. Una indicación de dato faltante dentro de su pantalla no es un cuarto aviso global.
- Mantén formularios y confirmaciones cuando previenen errores de dinero; reduce pasos de navegación, no verificación.

## Entrega

Ediciones pequeñas en SPA sin dependencias ni build. Comprueba foco visible, móvil, `prefers-reduced-motion`, `node --check static/app.js` y `python -m pytest tests/ -q` con BD temporal. Jamás toques `inversor.db`, respaldos o `.secrets/`. No despliegues públicamente la app de un usuario sin autenticación.
