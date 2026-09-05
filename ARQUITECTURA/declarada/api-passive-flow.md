# DECLARADA · `GET /api/passive-flow`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-passive-flow.md`](../rutas/api-passive-flow.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P4.7** — ¿Hay flujo pasivo absorbiendo en mi contra?  
  <sub>`entregas/20260904-2100-bateria-trader.md:174`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:5822

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **2 010 B**:

**PROMESA 1 · publica su instante Y el precio con el que decidio.**
`as_of` y `price = 79665.2` en primer nivel. La ubicacion (`location = "en_valor"`) es
relativa al `value_area`, y con el precio publicado se puede re-derivar: `poc`, `vah`, `val`
estan los tres.

**PROMESA 2 · el resultado va por HORIZONTES, no agregado.**
`horizons = {15m, 1h, 4h, 8h}` y `counts` con las tres categorias
(`reacumulacion_silenciosa`, `redistribucion_silenciosa`, `neutral`). El `summary` es un
resumen **al lado** del detalle, no en su lugar.

**PROMESA 3 · declara que es una INFERENCIA.**
`note = "manos silenciosas inferidas por abs…"`. Contesta **P4.7** —*"¿hay flujo pasivo
absorbiendo en mi contra?"*— y al mismo tiempo avisa de que la respuesta es inferida y no
observada. Es el ¶19 publicado en el cuerpo.

*Que significa no cumplirlo:* que `summary` viniera sin `counts`. Un "neutral" que sale de
2 de 4 horizontes y otro que sale de 4 de 4 serian el mismo texto.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1579`
