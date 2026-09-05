# DECLARADA · `GET /api/structure-detail`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-structure-detail.md`](../rutas/api-structure-detail.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.2** — ¿Cuál es la tendencia en 15m, 1h, 4h y diario?  
  <sub>`entregas/20260904-2100-bateria-trader.md:114`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:2318

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **2 929 B**. Publica `symbol`, `as_of` y `horizons`.

**PROMESA · es el detalle POR HORIZONTE de lo que `/api/structure` resume por capa.**
Las dos publican `as_of` de primer nivel y las dos cuelgan de la misma logica; la diferencia
es la granularidad, y por eso **P1.2 pide compararlas**: *"COHERENCIA ENTRE RUTAS: comparar
contra `structure` y `structure-detail`. Tres rutas hablan de lo mismo."*

**PENDIENTE · y el motivo es que la comparacion NO se puede hacer con una foto sola.**

La bateria pide cruzar tres rutas, y el operador ya publico un aviso sobre exactamente esto:
*"publique 'invariante rota' comparando `structure_detail` de una foto contra
`structure_horizons` de OTRA"*. Con **una** foto simultanea si se puede — y la hay — pero
**no he leido el interior de `horizons`**, asi que no se con que claves comparar.

Peticion con parametros comprobados (`BTCUSDT_PERP.A`, no `BTCUSDT`):

```sh
harness/bin/api '/api/structure-detail?symbol=BTCUSDT_PERP.A' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(list(d['horizons'].keys())); print(d['horizons'][list(d['horizons'])[0]])"
harness/bin/api '/api/structure?symbol=BTCUSDT_PERP.A' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([l['horizon'] for l in d['layers']])"
```

**Lo que hay que mirar:** si los horizontes de las dos rutas son el mismo conjunto. Si
`structure` agrupa en 3 capas lo que `structure-detail` da en 6 horizontes, la comparacion
de P1.2 necesita saber **como** se agrupa, y eso tiene que estar publicado o es K.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1480`, `static/app.js:1582`
