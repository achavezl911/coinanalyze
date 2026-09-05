# DECLARADA · `GET /api/data-confidence`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-data-confidence.md`](../rutas/api-data-confidence.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P0.10** — ¿La confianza que declara el Dashboard se deriva o se escribe a mano?  
  <sub>`entregas/20260904-2100-bateria-trader.md:102`</sub>
- **P0.2** — ¿Hay algún agujero en el histórico que estoy mirando?  
  <sub>`entregas/20260904-2100-bateria-trader.md:94`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (5), dentro de filas o bloques:

- `rows[].collectors_stale` (nombre)
- `rows[].combined_book_lag_seconds` (nombre)
- `rows[].flow_8h_futures_end_gap_seconds` (nombre)
- `rows[].flow_8h_spot_end_gap_seconds` (nombre)
- `rows[].snapshot_lag_seconds` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 5 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**PROMESA · cuenta VENUES VIVOS por tipo de dato, no una confianza agregada.**
En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z) devuelve `rows = [3]` —una por simbolo— con `snapshot_lag_seconds`,
**`spot_venues_live`**, **`futures_venues_live`**, **`book_venues_live`** y
`combined_book_lag_seconds`.

Contesta **P0.6** —*"¿cuantos venues respaldan esta cifra?"*— y de la unica forma que sirve:
**tres recuentos separados**, porque un venue puede estar vivo para trades y muerto para el
libro. Y contesta **P0.10** —*"¿la confianza se deriva o se escribe a mano?"*— publicando
los ingredientes en vez de una nota global: aqui no hay ningun campo `confidence` que
pudiera ser una constante.

*Que significa no cumplirlo:* que apareciera un unico `confidence: "alta"`. La bateria es
explicita: *"si es una constante o un COALESCE, no es confianza: es decoracion"*.

**NO publica su propio instante**, y es una de las 26 rutas de la foto que solo fechan sus
filas: `snapshot_lag_seconds` es un retraso, no una marca. Un consumidor puede saber cuanto
hace del snapshot, pero no de cuando es esta respuesta.

**La llama el panel** (`static/app.js:1493` y `:1621`), asi que su lectura llega al trader.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1493`, `static/app.js:1621`
- **readme**: `README.md:501`
