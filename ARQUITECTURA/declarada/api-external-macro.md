# DECLARADA · `GET /api/external-macro`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-external-macro.md`](../rutas/api-external-macro.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves de **primer nivel** — la respuesta declara su propio instante o periodo:

- `as_of` (nombre)
- `fetched_at` (nombre)

Claves **anidadas** (2), dentro de filas o bloques:

- `event_risk.next_event.event_at` (nombre)
- `event_risk.upcoming[].event_at` (nombre)

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 4 claves temporales en total.</sub>

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **3 467 B**:

**PROMESA 1 · publica DOS instantes con significados distintos.**
`as_of = "2026-09-04"` (el dia del dato macro) y
`fetched_at = "2026-09-04T22:15:20.229197+00:00"` (cuando se trajo). Un dato macro diario
traido a las 22:15 **no es un dato de las 22:15**, y separarlos es lo que impide leerlo mal.

**PROMESA 2 · declara sus FUENTES por nombre.** `sources = [4]`, la primera
`"FRED / Federal Reserve"`. Y `method = "Reglas deterministas de cambio a 5/…"`: la
clasificacion de regimen es reproducible porque el metodo esta publicado.

**PROMESA 3 · publica su cobertura Y su confianza, y la confianza NO es una constante.**
`coverage_pct = 100` junto a `data_confidence = "alta"`. La bateria avisa en **P0.10**:
*"si es una constante o un COALESCE, no es confianza: es decoracion"*. Aqui va con el
`coverage_pct` al lado, asi que se puede comprobar que se mueven juntos.

**PROMESA 4 · declara lo que NO puede medir.**
`limitations = [1]: "Flujos ETF requieren COINGLASS_API_…"`, y `institutional_flows` lleva
su propio `available` y `configured`. Un flujo de 0 por falta de clave y un flujo de 0
medido **no son el mismo cero** — es **P0.5**, y la ruta lo distingue con dos campos.

*Que significa no cumplirlo:* que `institutional_flows` publicara ceros sin `configured`.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1483`, `static/app.js:1637`
- **tests**: `tests/test_dashboard_layout.py:108`
