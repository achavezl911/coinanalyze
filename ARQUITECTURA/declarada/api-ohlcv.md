# DECLARADA · `GET /api/ohlcv`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-ohlcv.md`](../rutas/api-ohlcv.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['interval', 'limit']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (8), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.sources.ohlcv_1min` (sufijo de periodo)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)
- `data_gaps.window_end` (nombre)
- `data_gaps.window_start` (nombre)
- `rows[].bucket` (valor ISO)
- `rows[].last_sample` (valor ISO)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 8 claves temporales en total.</sub>

## PROMESA

### Las series de familia 2 comparten contrato, y se declaran juntas

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): **576 velas de 5 min** publica `symbol`, `interval`, `rows`, y ademas
**`coverage`** y **`data_gaps`** — los dos ultimos son el contrato de la familia y valen
mas que las filas.

**PROMESA 1 · declara LA VENTANA QUE SIRVIO, no la que le pidieron.**
`coverage = {served_window}`. Un `limit` es una peticion; `served_window` es lo que
hay. La ruta no deja que el consumidor deduzca la ventana contando filas — que es lo que
haria si `rows` viniera solo.

*Que significa no cumplirlo:* que `coverage` desapareciera. Entonces una serie corta por
falta de dato y una serie corta porque se pidio poco serian indistinguibles, y cualquier
tasa calculada encima tendria un denominador supuesto. Es **P5.2** llevado a las series.

**PROMESA 2 · publica SUS HUECOS, no solo sus filas.**
`data_gaps` trae `feed`, `exchanges`, `market`, `symbol`, `window_start`, `window_end`… Es
la respuesta a **P0.2** —*"¿hay algun agujero en el historico que estoy mirando?"*— y la
bateria le pone un caso concreto: **las 38 h del 08-28/29**. Una serie que publica sus
huecos permite preguntar; una que los omite obliga a fiarse.

**PROMESA 3 · el hueco declarado ENMASCARA el valor, no lo maquilla.**
Es lo que hace `mask_gapped_series_rows` (`app/api.py:679-689`), y el codigo lo explica:

> *"Un bucket con hueco declarado no puede seguir devolviendo precios como si nada:
> `sample_count` y `coverage_pct` son material para ADIVINAR la cobertura, y adivinar es
> justo lo que el panel no debe tener que hacer. Aqui la vela entera se pone a null, que es
> una afirmacion y no una pista."*

*Que significa no cumplirlo:* devolver el ultimo valor conocido en un bucket con hueco. Es
**P0.9** —*"si el proveedor esta caido, ¿me entero o veo el ultimo valor congelado?"*— y la
diferencia entre `null` y un numero rancio es la diferencia entre saberlo y no saberlo.

### Lo propio de esta ruta

**PROMESA · cada vela dice si esta COMPLETA y si esta CERRADA, y son dos cosas distintas.**
El SQL las publica como campos (`app/api.py:657-663`): `is_complete` (`sample_count =
expected_count`), `is_closed` (`bucket + interval <= now()`) y `coverage_pct`. El codigo lo
razona en el propio fichero:

> *"Una vela derivada no es una vela cerrada. Sin estos campos, un bucket con 2 de 5 minutos
> (o el que esta abriendose ahora) era indistinguible de uno completo y alimentaba ATR,
> estructura, rupturas y perfiles."*

*Que significa no cumplirlo:* que la vela en curso entrara en un ATR como si estuviera
cerrada. El error no se ve en la vela: se ve en las cuatro cosas que la consumen.

Es la unica serie de las cuatro que publica los tres campos.

### Y esa cobertura NO esta en la tabla · quien puede confiar en ella

`is_complete`, `is_closed` y `coverage_pct` **los calcula la CONSULTA de esta ruta**
(`app/api.py:657-663`), no la tabla. Medido contra el catalogo del esquema: las columnas de
`ohlcv` son `ts, symbol, interval, open, high, low, close, volume, buy_volume, sell_volume,
delta, tx, btx` — **ninguna de cobertura**.

**Eso decide quien puede confiar en ella:** la cobertura de `ohlcv` **solo existe para quien
pase por `/api/ohlcv`**. Cualquier consumidor que lea la tabla directamente —un colector,
una consulta de auditoria, otra ruta— **no tiene forma de saber si un bucket esta completo**,
porque el dato no esta guardado en ningun sitio: se deriva al servir.

*Que significa:* no es un defecto de esta ruta —hace mas de lo que la tabla le da—, pero es
una asimetria que hay que conocer antes de comparar cifras de `ohlcv` obtenidas por caminos
distintos. Contrasta con `spot_trades_agg`, que **si** guarda su `covered_seconds` y por
tanto se lo cuenta a todo el mundo.


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K20-cincoxx.sh:68`, `harness/checks/K31-eslabon5.sh:64`
- **panel**: `static/app.js:1492`
- **readme**: `README.md:402`
- **tests**: `tests/test_p1_timeframes_and_spot.py:52`
