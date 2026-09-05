# DECLARADA · `GET /api/quality/feeds`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-quality-feeds.md`](../rutas/api-quality-feeds.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P0.3** — ¿El colector que produce esto está vivo AHORA?  
  <sub>`entregas/20260904-2100-bateria-trader.md:95`</sub>
- **P0.8** — ¿Cuándo fue el último dato REAL de cada feed, no el último calculado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:100`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves de **primer nivel** — la respuesta declara su propio instante o periodo:

- `generated_at` (nombre)
- `window_seconds` (nombre)

Claves **anidadas** (11), dentro de filas o bloques:

- `collectors.api.lag_seconds` (nombre)
- `collectors.api.stale_after_seconds` (nombre)
- `collectors.daily.lag_seconds` (nombre)
- `collectors.daily.stale_after_seconds` (nombre)
- `collectors.ingest.lag_seconds` (nombre)
- `collectors.ingest.stale_after_seconds` (nombre)
- `collectors.scalp.lag_seconds` (nombre)
- `collectors.scalp.stale_after_seconds` (nombre)
- _… y 3 mas_

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 13 claves temporales en total.</sub>

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1623`
- **readme**: `README.md:32`
