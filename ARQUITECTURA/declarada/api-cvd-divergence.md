# DECLARADA · `GET /api/cvd/divergence`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-cvd-divergence.md`](../rutas/api-cvd-divergence.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P5.6** — ¿Hay divergencias activas y qué han valido históricamente?  
  <sub>`entregas/20260904-2100-bateria-trader.md:190`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['interval', 'limit']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (5), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.sources.ohlcv_1min` (sufijo de periodo)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)
- `rows[].bucket` (valor ISO)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 5 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**PENDIENTE, y el motivo no es el tiempo: no he leido su cuerpo en la foto.**

Es la gemela de `/api/divergences` para **P5.6**, y la diferencia entre las dos es
justamente lo que la bateria persigue en P1.2: **dos rutas que hablan de lo mismo**. La
ficha derivada dice que lee `spot_trades_agg` y `ohlcv`, o sea que su divergencia es
**precio contra CVD spot**.

Peticion con parametros comprobados, y **las dos juntas**, que es como se compara:

```sh
harness/bin/api '/api/cvd/divergence?symbol=BTCUSDT_PERP.A' > /tmp/cvddiv.json
harness/bin/api '/api/divergences?symbol=BTCUSDT_PERP.A'    > /tmp/div.json
wc -c /tmp/cvddiv.json /tmp/div.json
python3 -c "import json;print(sorted(json.load(open('/tmp/cvddiv.json'))));print(sorted(json.load(open('/tmp/div.json'))))"
```

**Lo que hay que mirar:** si las dos rutas, para el mismo instante, dicen lo mismo sobre la
misma divergencia. Si difieren y **ninguna declara su ventana**, la discrepancia no se puede
atribuir ni a un defecto ni a una deriva — que es exactamente el error que el operador
cometio y publico: comparar dos fotos distintas creyendo comparar dos rutas.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1547`
- **readme**: `README.md:405`
