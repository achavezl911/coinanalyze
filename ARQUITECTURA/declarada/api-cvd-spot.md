# DECLARADA · `GET /api/cvd/spot`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-cvd-spot.md`](../rutas/api-cvd-spot.md).
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

Claves **anidadas** (6), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)
- `data_gaps.window_end` (nombre)
- `data_gaps.window_start` (nombre)
- `rows[].bucket` (valor ISO)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 6 claves temporales en total.</sub>

## PROMESA


### Lo que promete

Es **la gemela spot de `/api/cvd`** y comparte su contrato entero: `symbol`, `interval`,
`rows = [576]` con `bucket`/`delta_usd`/`cvd`, mas `coverage.served_window` y `data_gaps`.
Ver la ficha de `/api/cvd` para las tres promesas de la familia.

**PROMESA propia · publica el CVD de spot como serie separada del de futuros, y esa
separacion es la que hace posible la pregunta.**
`/api/cvd` (futuros) y esta (spot) son dos rutas y no una con un parametro. La bateria mide
en **P1.1** que *"el diferencial spot-futuros NO vota direccion"*, y esa comprobacion solo se
puede hacer si las dos series se pueden pedir **por separado y con el mismo `interval`**.

*Que significa no cumplirlo:* fundirlas en una ruta con `market=spot|perp`. Se seguiria
pudiendo, pero se perderia la garantia de que las dos usan el mismo bucket — y el diferencial
de dos series con distinto bucket no significa nada.

**Y es una de las 6 rutas SIN NINGUN RASTRO en el repo** (ver la ficha derivada): nadie la
llama, ni el panel ni un check. Su dato llega al producto por `/api/cvd/divergence` y por
`spot_trades_agg`, que leen 10 rutas.


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:404`
